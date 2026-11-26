"""Concept2 Logbook API adapter for indoor rower and erg bike workouts."""

from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any
from zoneinfo import ZoneInfo
import httpx

from src.adapters.base import (
    BaseIngestionAdapter,
    NormalizedHeartRateSample,
    NormalizedSplit,
    NormalizedWorkout,
    SyncBatchResult,
)
from src.core.config import settings
from src.core.http_client import request_with_retry
from src.core.logging import redact_secrets

logger = logging.getLogger(__name__)


def _parse_c2_time_sec(raw_val: Any) -> float:
    """Convert Concept2 duration values (always tenths of a second in the Logbook API) to seconds."""
    if raw_val is None or raw_val == "":
        return 0.0
    return round(float(raw_val) / 10.0, 2)


def _truncate_tenth(val: float) -> float:
    """Truncate a floating-point value down to one decimal place (matches Concept2 Logbook display)."""
    return math.floor(val * 10.0 + 1e-9) / 10.0


def parse_concept2_strokes(
    raw_data: dict[str, Any],
    strokes_data: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Align Concept2 stroke telemetry with workout intervals and cumulative elapsed time."""
    strokes = strokes_data if strokes_data is not None else (raw_data.get("strokes") or [])
    if not strokes:
        return []

    raw_intervals = raw_data.get("intervals") or raw_data.get("workout", {}).get("intervals") or []
    interval_offsets: list[float] = []
    cur_offset = 0.0
    for idx, inv in enumerate(raw_intervals):
        interval_offsets.append(cur_offset)
        cur_offset += _parse_c2_time_sec(inv.get("time", 0))
        if idx < len(raw_intervals) - 1:
            cur_offset += _parse_c2_time_sec(inv.get("rest_time", 0))

    aligned: list[dict[str, Any]] = []
    seg_idx = 0
    prev_t = -1.0
    for s in strokes:
        t_raw = float(s.get("t", 0))
        if prev_t >= 0 and t_raw < prev_t:
            seg_idx += 1
        prev_t = t_raw

        rel_sec = round(t_raw / 10.0, 1)
        offset_sec = interval_offsets[seg_idx] if seg_idx < len(interval_offsets) else 0.0
        abs_sec = round(offset_sec + rel_sec, 1)

        p_raw = s.get("p")
        pace_sec = round(float(p_raw) / 10.0, 1) if p_raw and float(p_raw) > 0 else None

        hr_raw = s.get("hr")
        hr_bpm = int(hr_raw) if hr_raw and int(hr_raw) > 30 else None

        spm_raw = s.get("spm")
        cadence_spm = float(spm_raw) if spm_raw is not None else None

        aligned.append(
            {
                "interval_index": seg_idx + 1,
                "set_elapsed_sec": rel_sec,
                "elapsed_sec": abs_sec,
                "heart_rate": hr_bpm,
                "pace_sec": pace_sec,
                "cadence_spm": cadence_spm,
            }
        )

    return aligned


class Concept2Adapter(BaseIngestionAdapter):
    """Client for Concept2 Logbook API."""

    AUTH_URL = "https://log.concept2.com/oauth/authorize"
    TOKEN_URL = "https://log.concept2.com/oauth/access_token"  # noqa: S105
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
        return str(httpx.URL(self.AUTH_URL, params=params))

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await request_with_retry(client, "POST", self.TOKEN_URL, data=data)
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
            resp = await request_with_retry(client, "POST", self.TOKEN_URL, data=data)
            resp.raise_for_status()
            return resp.json()

    async def verify_connection(self, access_token: str) -> dict[str, Any]:
        """Tests connectivity to Concept2 Logbook API using the stored access token."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await request_with_retry(
                    client,
                    "GET",
                    f"{self.BASE_URL}/users/me",
                    headers=headers,
                    max_attempts=2,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    username = data.get("username") or data.get("first_name", "Concept2 User")
                    return {
                        "is_connected": True,
                        "status": "healthy",
                        "athlete_name": username,
                        "error": None,
                    }
                elif resp.status_code == 401:
                    return {
                        "is_connected": False,
                        "status": "expired",
                        "athlete_name": None,
                        "error": "Access token expired or revoked.",
                    }
                else:
                    return {
                        "is_connected": False,
                        "status": "error",
                        "athlete_name": None,
                        "error": f"Concept2 API error: HTTP {resp.status_code}",
                    }
        except Exception as exc:
            return {
                "is_connected": False,
                "status": "error",
                "athlete_name": None,
                "error": redact_secrets(str(exc)),
            }

    def normalize_concept2_workout(
        self,
        raw_data: dict[str, Any],
        strokes_data: list[dict[str, Any]] | None = None,
    ) -> NormalizedWorkout:
        """Map raw Concept2 Logbook workout JSON to canonical NormalizedWorkout entity."""
        raw_id = raw_data.get("id")
        if raw_id is None or str(raw_id).strip() == "":
            raise ValueError("Concept2 workout payload missing required 'id' field.")
        ext_id = str(raw_id).strip()

        raw_type = str(raw_data.get("type", "rower")).lower()
        if "bike" in raw_type:
            discipline = "erg_bike"
            title = "Concept2 BikeErg Session"
        else:
            discipline = "indoor_row"
            title = "Concept2 Indoor Rower Session"

        timezone_str = raw_data.get("timezone", "UTC")
        date_utc_str = raw_data.get("date_utc")
        date_str = raw_data.get("date")
        if date_utc_str:
            try:
                start_time_utc = datetime.fromisoformat(date_utc_str.replace("Z", "+00:00"))
                if start_time_utc.tzinfo is None:
                    start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)
            except Exception:
                start_time_utc = datetime.now(timezone.utc)
        elif date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    if timezone_str and timezone_str != "UTC":
                        try:
                            dt = dt.replace(tzinfo=ZoneInfo(timezone_str)).astimezone(timezone.utc)
                        except Exception:
                            dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.replace(tzinfo=timezone.utc)
                start_time_utc = dt.astimezone(timezone.utc)
            except Exception:
                start_time_utc = datetime.now(timezone.utc)
        else:
            start_time_utc = datetime.now(timezone.utc)

        # Concept2 time is always in tenths of a second
        total_duration_sec = _parse_c2_time_sec(raw_data.get("time", 0))
        distance_m = float(raw_data.get("distance", 0.0))

        # Concept2 pace is tenths of a second per 500m (rower) OR per 1000m (BikeErg)
        raw_pace = raw_data.get("pace")
        if discipline == "erg_bike":
            avg_pace_km = (
                round(float(raw_pace) / 10.0, 1)
                if raw_pace
                else (
                    _truncate_tenth((total_duration_sec / distance_m) * 1000.0)
                    if distance_m > 0 and total_duration_sec > 0
                    else None
                )
            )
            avg_split_500m = None
        else:
            avg_split_500m = (
                round(float(raw_pace) / 10.0, 1)
                if raw_pace
                else (
                    _truncate_tenth((total_duration_sec / distance_m) * 500.0)
                    if distance_m > 0 and total_duration_sec > 0
                    else None
                )
            )
            avg_pace_km = None

        stroke_rate = raw_data.get("stroke_rate")
        stroke_count = raw_data.get("stroke_count")
        watts = raw_data.get("watts")
        drag_factor = raw_data.get("drag_factor")
        calories = raw_data.get("calories") or raw_data.get("calories_total")

        hr_info = raw_data.get("heart_rate") or {}
        if isinstance(hr_info, dict):
            avg_hr = hr_info.get("average")
            max_hr = hr_info.get("max")
        else:
            avg_hr = int(hr_info) if hr_info else None
            max_hr = None

        splits: list[NormalizedSplit] = []
        raw_intervals = raw_data.get("intervals") or raw_data.get("workout", {}).get("intervals")
        is_interval_workout = bool(raw_intervals)
        raw_segments = raw_intervals or raw_data.get("workout", {}).get("splits") or []
        segment_type = "interval" if is_interval_workout else "lap"

        total_wattminutes = 0.0
        for i, interval in enumerate(raw_segments):
            idx = int(interval.get("index", len(splits) + 1))
            inv_dist = float(interval.get("distance", 0.0))
            inv_duration_sec = _parse_c2_time_sec(interval.get("time", 0))

            inv_pace_raw = interval.get("pace")
            if discipline == "erg_bike":
                if inv_pace_raw:
                    inv_pace_km = round(float(inv_pace_raw) / 10.0, 1)
                    inv_split_500m = round(inv_pace_km / 2.0, 1)
                elif inv_dist > 0 and inv_duration_sec > 0:
                    inv_pace_km = _truncate_tenth((inv_duration_sec / inv_dist) * 1000.0)
                    inv_split_500m = round(inv_pace_km / 2.0, 1)
                else:
                    inv_pace_km = None
                    inv_split_500m = None
            else:
                if inv_pace_raw:
                    inv_split_500m = round(float(inv_pace_raw) / 10.0, 1)
                elif inv_dist > 0 and inv_duration_sec > 0:
                    inv_split_500m = _truncate_tenth((inv_duration_sec / inv_dist) * 500.0)
                else:
                    inv_split_500m = None
                inv_pace_km = (
                    _truncate_tenth((inv_duration_sec / inv_dist) * 1000.0)
                    if inv_dist > 0 and inv_duration_sec > 0
                    else ((inv_split_500m * 2.0) if inv_split_500m else None)
                )

            inv_wm = interval.get("wattminutes_total")
            inv_watts = interval.get("watts")
            if inv_wm and inv_duration_sec > 0:
                inv_watts = round((float(inv_wm) * 60.0) / inv_duration_sec, 1)
                total_wattminutes += float(inv_wm)
            elif inv_watts is None and inv_dist > 0 and inv_duration_sec > 0:
                if discipline == "indoor_row":
                    exact_split = (inv_duration_sec / inv_dist) * 500.0
                    inv_watts = round(2.8 / ((exact_split / 500.0) ** 3), 1)
            else:
                inv_watts = float(inv_watts) if inv_watts is not None else None

            inv_hr_raw = interval.get("heart_rate")
            inv_avg_hr = (
                inv_hr_raw.get("average")
                if isinstance(inv_hr_raw, dict)
                else (int(inv_hr_raw) if inv_hr_raw is not None else None)
            )

            splits.append(
                NormalizedSplit(
                    split_index=idx,
                    distance_m=inv_dist,
                    duration_sec=inv_duration_sec,
                    split_type=segment_type,
                    avg_power_watts=inv_watts,
                    avg_cadence_spm=float(interval.get("stroke_rate")) if interval.get("stroke_rate") is not None else None,
                    avg_heart_rate=inv_avg_hr,
                    avg_split_sec_per_500m=inv_split_500m,
                    avg_pace_sec_per_km=inv_pace_km,
                )
            )

            # Append rest split ONLY between work intervals (never a trailing rest after final interval)
            if is_interval_workout and i < len(raw_segments) - 1:
                rest_sec = _parse_c2_time_sec(interval.get("rest_time", 0))
                if rest_sec > 0:
                    rest_hr = inv_hr_raw.get("rest") if isinstance(inv_hr_raw, dict) else None
                    splits.append(
                        NormalizedSplit(
                            split_index=len(splits) + 1,
                            distance_m=0.0,
                            duration_sec=rest_sec,
                            split_type="rest",
                            avg_power_watts=0.0,
                            avg_cadence_spm=0.0,
                            avg_heart_rate=int(rest_hr) if rest_hr else None,
                            avg_split_sec_per_500m=None,
                            avg_pace_sec_per_km=None,
                        )
                    )

        hr_samples: list[NormalizedHeartRateSample] = []
        summary_to_save = dict(raw_data)
        effective_strokes = strokes_data if strokes_data is not None else raw_data.get("strokes")

        if effective_strokes:
            summary_to_save["strokes"] = effective_strokes
            aligned_strokes = parse_concept2_strokes(raw_data, effective_strokes)
            for st in aligned_strokes:
                hr_val = st["heart_rate"]
                if hr_val is not None:
                    sec = st["elapsed_sec"]
                    hr_samples.append(
                        NormalizedHeartRateSample(
                            elapsed_sec=sec,
                            bpm=hr_val,
                            timestamp_utc=start_time_utc + timedelta(seconds=sec),
                        )
                    )
        elif splits:
            cur_sec = 0.0
            for sp in splits:
                if sp.avg_heart_rate and sp.duration_sec and sp.duration_sec > 0:
                    step = 10.0
                    n_steps = max(1, int(sp.duration_sec / step))
                    for j in range(n_steps):
                        sample_sec = cur_sec + (j * step)
                        hr_samples.append(
                            NormalizedHeartRateSample(
                                elapsed_sec=sample_sec,
                                bpm=sp.avg_heart_rate,
                                timestamp_utc=start_time_utc + timedelta(seconds=sample_sec),
                            )
                        )
                cur_sec += (sp.duration_sec or 0.0)
        elif avg_hr and total_duration_sec > 0:
            step = 15.0
            n_steps = max(2, int(total_duration_sec / step))
            for i in range(n_steps):
                sample_sec = min(total_duration_sec, i * step)
                hr_samples.append(
                    NormalizedHeartRateSample(
                        elapsed_sec=sample_sec,
                        bpm=int(avg_hr),
                        timestamp_utc=start_time_utc + timedelta(seconds=sample_sec),
                    )
                )

        if watts is None:
            if total_wattminutes > 0 and total_duration_sec > 0:
                watts = round((total_wattminutes * 60.0) / total_duration_sec, 1)
            elif distance_m > 0 and total_duration_sec > 0 and discipline == "indoor_row":
                exact_avg_split = (total_duration_sec / distance_m) * 500.0
                watts = round(2.8 / ((exact_avg_split / 500.0) ** 3), 1)

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
            avg_pace_sec_per_km=avg_pace_km,
            avg_split_sec_per_500m=avg_split_500m,
            avg_drag_factor=int(drag_factor) if drag_factor is not None else None,
            raw_summary=summary_to_save,
            splits=splits,
            heart_rate_samples=hr_samples,
        )

    async def fetch_workouts_batch(
        self,
        access_token: str,
        cursor: dict[str, Any] | None = None,
        since: datetime | None = None,
    ) -> SyncBatchResult:
        """Fetch workouts from Concept2 Logbook API, propagating HTTP errors for honest retry/refresh."""
        page = cursor.get("page", 1) if cursor else 1
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        params: dict[str, Any] = {"page": page}
        if since:
            params["from"] = since.strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/users/me/results"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await request_with_retry(client, "GET", url, headers=headers, params=params)
            if resp.status_code == 404:
                return SyncBatchResult(workouts=[], next_cursor=None, has_more=False)
            resp.raise_for_status()
            payload = resp.json()

            results_data = payload.get("data", [])
            normalized_workouts: list[NormalizedWorkout] = []
            for item in results_data:
                strokes_data = None
                if item.get("stroke_data") is True:
                    try:
                        res_id = item.get("id")
                        s_url = f"{self.BASE_URL}/users/me/results/{res_id}/strokes"
                        s_resp = await request_with_retry(client, "GET", s_url, headers=headers, max_attempts=2)
                        if s_resp.status_code == 200:
                            s_json = s_resp.json()
                            strokes_data = s_json.get("data") if isinstance(s_json, dict) else s_json
                    except Exception:
                        strokes_data = None

                try:
                    normalized_workouts.append(self.normalize_concept2_workout(item, strokes_data=strokes_data))
                except ValueError as val_exc:
                    logger.warning("Skipping malformed Concept2 workout: %s", val_exc)

            pagination = payload.get("pagination", {})
            has_next = bool(pagination.get("next"))
            next_cursor = {"page": page + 1} if has_next else None

            return SyncBatchResult(
                workouts=normalized_workouts,
                next_cursor=next_cursor,
                has_more=has_next,
            )
