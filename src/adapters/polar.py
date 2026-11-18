"""Polar AccessLink API adapter for outdoor running workouts."""

import base64
from datetime import datetime, timezone
import re
from typing import Any
import httpx

from src.adapters.base import (
    BaseIngestionAdapter,
    NormalizedGPSPoint,
    NormalizedHeartRateSample,
    NormalizedWorkout,
    SyncBatchResult,
)
from src.core.config import settings


def parse_iso_duration(duration_str: str | float | int) -> float:
    """Parse duration in seconds or ISO 8601 string (e.g. PT3600S or PT1H30M15S)."""
    if isinstance(duration_str, (int, float)):
        return float(duration_str)
    if not isinstance(duration_str, str):
        return 0.0

    match = re.match(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?",
        duration_str,
    )
    if not match:
        try:
            return float(duration_str)
        except ValueError:
            return 0.0

    parts = match.groupdict()
    hours = float(parts["hours"] or 0)
    minutes = float(parts["minutes"] or 0)
    seconds = float(parts["seconds"] or 0)
    return hours * 3600 + minutes * 60 + seconds


class PolarAdapter(BaseIngestionAdapter):
    """Client for Polar AccessLink API."""

    AUTH_URL = "https://flow.polar.com/oauth2/authorization"
    TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
    BASE_URL = "https://polarremote.com/v2"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ):
        self.client_id = client_id or settings.POLAR_CLIENT_ID
        self.client_secret = client_secret or settings.POLAR_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.POLAR_REDIRECT_URI

    def get_authorization_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        query = "&".join(f"{k}={httpx.URL('', params={k: v}).query.decode()}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.TOKEN_URL, headers=headers, data=data)
            resp.raise_for_status()
            return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        # Polar tokens are typically long-lived user tokens, but we implement standard OAuth refresh
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.TOKEN_URL, headers=headers, data=data)
            resp.raise_for_status()
            return resp.json()

    def normalize_polar_exercise(
        self, exercise_data: dict[str, Any], samples_data: dict[str, Any] | None = None
    ) -> NormalizedWorkout:
        """Map raw Polar exercise JSON to canonical NormalizedWorkout entity."""
        ext_id = str(exercise_data.get("id"))
        device = exercise_data.get("device", "Polar Watch")
        title = f"Polar Run - {device}"

        start_time_str = exercise_data.get("start_time")
        if start_time_str:
            start_time_utc = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        else:
            start_time_utc = datetime.now(timezone.utc)

        duration_sec = parse_iso_duration(exercise_data.get("duration", 0))
        distance_m = float(exercise_data.get("distance", 0.0))

        # Pace calculation in sec/km
        avg_pace = None
        if distance_m > 0 and duration_sec > 0:
            avg_pace = duration_sec / (distance_m / 1000.0)

        hr_info = exercise_data.get("heart_rate") or {}
        avg_hr = hr_info.get("average")
        max_hr = hr_info.get("maximum")

        elevation_gain = exercise_data.get("ascent")
        elevation_loss = exercise_data.get("descent")
        calories = exercise_data.get("calories")

        # Parse telemetry streams
        hr_samples: list[NormalizedHeartRateSample] = []
        gps_points: list[NormalizedGPSPoint] = []

        if samples_data:
            # HR samples
            for sample in samples_data.get("heart_rate", []):
                sec = float(sample.get("elapsed_sec", 0))
                bpm = int(sample.get("bpm", 0))
                hr_samples.append(
                    NormalizedHeartRateSample(
                        elapsed_sec=sec,
                        bpm=bpm,
                        timestamp_utc=start_time_utc,
                    )
                )

            # GPS route points
            for pt in samples_data.get("coordinates", []):
                sec = float(pt.get("elapsed_sec", 0))
                lat = float(pt.get("latitude", 0.0))
                lon = float(pt.get("longitude", 0.0))
                alt = pt.get("altitude")
                alt_m = float(alt) if alt is not None else None
                gps_points.append(
                    NormalizedGPSPoint(
                        elapsed_sec=sec,
                        latitude=lat,
                        longitude=lon,
                        altitude_m=alt_m,
                        timestamp_utc=start_time_utc,
                    )
                )

        return NormalizedWorkout(
            provider="polar",
            external_id=ext_id,
            discipline="outdoor_run",
            title=title,
            start_time_utc=start_time_utc,
            local_timezone="UTC",
            total_duration_sec=duration_sec,
            active_duration_sec=duration_sec,
            total_distance_m=distance_m,
            total_calories=int(calories) if calories else None,
            avg_heart_rate=int(avg_hr) if avg_hr else None,
            max_heart_rate=int(max_hr) if max_hr else None,
            avg_pace_sec_per_km=avg_pace,
            elevation_gain_m=float(elevation_gain) if elevation_gain is not None else None,
            elevation_loss_m=float(elevation_loss) if elevation_loss is not None else None,
            raw_summary=exercise_data,
            heart_rate_samples=hr_samples,
            gps_route_points=gps_points,
        )

    async def register_user(self, access_token: str, member_id: str) -> dict[str, Any] | None:
        """Register a user with Polar AccessLink API (required once after OAuth authorization)."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/users",
                headers=headers,
                json={"member-id": member_id},
            )
            # 200 = registered, 409 = already registered
            if resp.status_code in (200, 409):
                return resp.json() if resp.status_code == 200 else None
            resp.raise_for_status()
            return resp.json()

    async def fetch_workouts_batch(
        self,
        access_token: str,
        cursor: dict[str, Any] | None = None,
        since: datetime | None = None,
    ) -> SyncBatchResult:
        """Pull new workouts and telemetry from Polar AccessLink using the Transaction API."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Create an exercise transaction to retrieve new exercises
            # Polar AccessLink transaction endpoint: POST /v2/users/{user_id}/exercise-transactions
            # When user_id is unknown or single-user token, Polar also supports pull via /v2/users/exercise-transactions
            # or direct query.
            user_id = cursor.get("user_id") if cursor else None
            tx_url = f"{self.BASE_URL}/users/{user_id}/exercise-transactions" if user_id else f"{self.BASE_URL}/users/exercise-transactions"

            try:
                tx_resp = await client.post(tx_url, headers=headers)
            except httpx.HTTPError:
                return SyncBatchResult(workouts=[], next_cursor=cursor, has_more=False)

            if tx_resp.status_code == 204:
                # 204 No Content: No new exercises available
                return SyncBatchResult(workouts=[], next_cursor=cursor, has_more=False)

            if tx_resp.status_code == 404 and not user_id:
                # Fallback if user_id is required: check userinfo or return empty
                return SyncBatchResult(workouts=[], next_cursor=cursor, has_more=False)

            tx_resp.raise_for_status()
            tx_data = tx_resp.json()
            transaction_id = tx_data.get("transaction-id")
            if not transaction_id:
                return SyncBatchResult(workouts=[], next_cursor=cursor, has_more=False)

            # Step 2: List exercises in the transaction
            exercises_resp = await client.get(
                f"{tx_url}/{transaction_id}",
                headers=headers,
            )
            exercises_resp.raise_for_status()
            exercise_urls: list[str] = exercises_resp.json().get("exercises", [])

            normalized_workouts: list[NormalizedWorkout] = []

            # Step 3: Fetch each exercise summary and its samples (HR & GPS)
            for ex_url in exercise_urls:
                ex_resp = await client.get(ex_url, headers=headers)
                if ex_resp.status_code != 200:
                    continue
                ex_data = ex_resp.json()

                # Fetch detailed samples (coordinates and heart rate)
                samples_data = None
                samples_url = f"{ex_url}/samples"
                samples_resp = await client.get(samples_url, headers=headers)
                if samples_resp.status_code == 200:
                    samples_data = samples_resp.json()

                workout = self.normalize_polar_exercise(ex_data, samples_data)
                normalized_workouts.append(workout)

            # Step 4: Commit transaction to mark exercises as processed
            await client.put(f"{tx_url}/{transaction_id}", headers=headers)

            return SyncBatchResult(
                workouts=normalized_workouts,
                next_cursor=cursor,
                has_more=False,
            )
