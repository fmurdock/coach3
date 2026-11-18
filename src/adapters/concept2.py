"""Concept2 Logbook API adapter for indoor rower and erg bike workouts."""

from datetime import datetime, timezone
from typing import Any
import httpx

from src.adapters.base import (
    BaseIngestionAdapter,
    NormalizedSplit,
    NormalizedWorkout,
    SyncBatchResult,
)
from src.core.config import settings


class Concept2Adapter(BaseIngestionAdapter):
    """Client for Concept2 Logbook API."""

    AUTH_URL = "https://log.concept2.com/oauth/authorize"
    TOKEN_URL = "https://log.concept2.com/oauth/access_token"
    BASE_URL = "https://log.concept2.com/api"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ):
        self.client_id = client_id or settings.CONCEPT2_CLIENT_ID
        self.client_secret = client_secret or settings.CONCEPT2_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.CONCEPT2_REDIRECT_URI

    def get_authorization_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:read,results:read",
            "state": state,
        }
        query = "&".join(f"{k}={httpx.URL('', params={k: v}).query.decode()}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            resp.raise_for_status()
            return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            resp.raise_for_status()
            return resp.json()

    def normalize_concept2_workout(self, raw_data: dict[str, Any]) -> NormalizedWorkout:
        """Map raw Concept2 Logbook workout JSON to canonical NormalizedWorkout entity."""
        ext_id = str(raw_data.get("id"))
        raw_type = str(raw_data.get("type", "rower")).lower()

        if "bike" in raw_type:
            discipline = "erg_bike"
            title = "Concept2 BikeErg Session"
        else:
            discipline = "indoor_row"
            title = "Concept2 Indoor Rower Session"

        date_str = raw_data.get("date")
        if date_str:
            try:
                # Format: "YYYY-MM-DD HH:MM:SS" or ISO
                start_time_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if start_time_utc.tzinfo is None:
                    start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)
            except Exception:
                start_time_utc = datetime.now(timezone.utc)
        else:
            start_time_utc = datetime.now(timezone.utc)

        timezone_str = raw_data.get("timezone", "UTC")

        # Concept2 time is in tenths of a second (e.g. 12000 = 1200.0 sec)
        raw_time = raw_data.get("time", 0)
        total_duration_sec = float(raw_time) / 10.0 if raw_time > 3600 and isinstance(raw_time, int) and raw_time % 10 == 0 else float(raw_time)
        if total_duration_sec > 100000:
            total_duration_sec = float(raw_time) / 10.0

        distance_m = float(raw_data.get("distance", 0.0))

        # Pace in C2 is tenths of a second per 500m (e.g. 1200 = 120.0s = 2:00 / 500m)
        raw_pace = raw_data.get("pace")
        avg_split_500m = float(raw_pace) / 10.0 if raw_pace else None

        stroke_rate = raw_data.get("stroke_rate")
        stroke_count = raw_data.get("stroke_count")
        watts = raw_data.get("watts")
        drag_factor = raw_data.get("drag_factor")
        calories = raw_data.get("calories")

        hr_info = raw_data.get("heart_rate") or {}
        if isinstance(hr_info, dict):
            avg_hr = hr_info.get("average")
            max_hr = hr_info.get("max")
        else:
            avg_hr = int(hr_info) if hr_info else None
            max_hr = None

        # Parse intervals / splits
        splits: list[NormalizedSplit] = []
        raw_intervals = raw_data.get("intervals") or []
        for interval in raw_intervals:
            idx = int(interval.get("index", len(splits) + 1))
            inv_dist = float(interval.get("distance", 0.0))
            inv_time_raw = interval.get("time", 0)
            inv_duration_sec = float(inv_time_raw) / 10.0 if inv_time_raw > 1000 else float(inv_time_raw)

            inv_pace_raw = interval.get("pace")
            inv_split_500m = float(inv_pace_raw) / 10.0 if inv_pace_raw else None

            splits.append(
                NormalizedSplit(
                    split_index=idx,
                    distance_m=inv_dist,
                    duration_sec=inv_duration_sec,
                    split_type="interval",
                    avg_power_watts=float(interval.get("watts")) if interval.get("watts") is not None else None,
                    avg_cadence_spm=float(interval.get("stroke_rate")) if interval.get("stroke_rate") is not None else None,
                    avg_heart_rate=int(interval.get("heart_rate")) if interval.get("heart_rate") is not None else None,
                    avg_split_sec_per_500m=inv_split_500m,
                )
            )

        return NormalizedWorkout(
            provider="concept2",
            external_id=ext_id,
            discipline=discipline,
            title=title,
            start_time_utc=start_time_utc,
            local_timezone=timezone_str,
            total_duration_sec=total_duration_sec,
            active_duration_sec=total_duration_sec,
            total_distance_m=distance_m,
            total_calories=int(calories) if calories else None,
            avg_heart_rate=int(avg_hr) if avg_hr else None,
            max_heart_rate=int(max_hr) if max_hr else None,
            total_strokes=int(stroke_count) if stroke_count else None,
            avg_cadence_spm=float(stroke_rate) if stroke_rate is not None else None,
            avg_power_watts=float(watts) if watts is not None else None,
            avg_split_sec_per_500m=avg_split_500m,
            avg_drag_factor=int(drag_factor) if drag_factor is not None else None,
            raw_summary=raw_data,
            splits=splits,
        )

    async def fetch_workouts_batch(
        self,
        access_token: str,
        cursor: dict[str, Any] | None = None,
        since: datetime | None = None,
    ) -> SyncBatchResult:
        return SyncBatchResult(workouts=[], next_cursor=None, has_more=False)
