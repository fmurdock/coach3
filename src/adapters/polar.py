"""Polar AccessLink API adapter for outdoor running workouts."""

import base64
from datetime import datetime, timedelta, timezone
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
    BASE_URL = "https://www.polaraccesslink.com/v3"

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
            "scope": "accesslink.read_all",
            "state": state,
        }
        return str(httpx.URL(self.AUTH_URL, params=params))

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

    async def verify_connection(self, access_token: str, user_id: str | None = None) -> dict[str, Any]:
        """Tests connectivity to Polar AccessLink using the stored access token."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        url = f"{self.BASE_URL}/users/{user_id}" if user_id else f"{self.BASE_URL}/users"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code in (200, 201):
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    first_name = data.get("first-name")
                    last_name = data.get("last-name")
                    if first_name or last_name:
                        athlete_name = f"{first_name or ''} {last_name or ''}".strip()
                    else:
                        athlete_id = str(data.get("polar-user-id", user_id or "Registered Athlete"))
                        athlete_name = f"Polar Athlete #{athlete_id}"
                    return {
                        "is_connected": True,
                        "status": "healthy",
                        "athlete_name": athlete_name,
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
                        "error": f"Polar API error: HTTP {resp.status_code}",
                    }
        except Exception as exc:
            return {
                "is_connected": False,
                "status": "error",
                "athlete_name": None,
                "error": str(exc),
            }

    def normalize_polar_exercise(
        self, exercise_data: dict[str, Any], samples_data: dict[str, Any] | None = None
    ) -> NormalizedWorkout:
        """Map raw Polar exercise JSON to canonical NormalizedWorkout entity."""
        ext_id = str(exercise_data.get("id"))
        device = exercise_data.get("device", "Polar Watch")
        title = f"Polar Run - {device}"

        start_time_str = exercise_data.get("start-time") or exercise_data.get("start_time")
        offset_min = exercise_data.get("start-time-utc-offset")
        if start_time_str:
            if "Z" in start_time_str or "+" in start_time_str or (len(start_time_str) > 19 and "-" in start_time_str[19:]):
                start_time_utc = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).astimezone(timezone.utc)
            elif offset_min is not None:
                tz = timezone(timedelta(minutes=int(offset_min)))
                start_time_utc = datetime.fromisoformat(start_time_str).replace(tzinfo=tz).astimezone(timezone.utc)
            else:
                start_time_utc = datetime.fromisoformat(start_time_str).replace(tzinfo=timezone.utc)
        else:
            start_time_utc = datetime.now(timezone.utc)

        duration_sec = parse_iso_duration(exercise_data.get("duration", 0))
        distance_m = float(exercise_data.get("distance", 0.0))

        # Pace calculation in sec/km
        avg_pace = None
        if distance_m > 0 and duration_sec > 0:
            avg_pace = duration_sec / (distance_m / 1000.0)

        hr_info = exercise_data.get("heart-rate") or exercise_data.get("heart_rate") or {}
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
            hr_list = samples_data.get("heart_rate") or samples_data.get("heart-rate") or []
            for sample in hr_list:
                sec = float(sample.get("elapsed_sec", sample.get("elapsed-sec", 0)))
                bpm = int(sample.get("bpm", 0))
                hr_samples.append(
                    NormalizedHeartRateSample(
                        elapsed_sec=sec,
                        bpm=bpm,
                        timestamp_utc=start_time_utc,
                    )
                )

            # GPS route points
            coord_list = samples_data.get("coordinates") or []
            for pt in coord_list:
                sec = float(pt.get("elapsed_sec", pt.get("elapsed-sec", 0)))
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
            # 200/201 = registered, 409 = already registered
            if resp.status_code in (200, 201, 409):
                return resp.json() if resp.status_code in (200, 201) else None
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

        user_id = (cursor.get("user_id") if cursor else None) or "me"

        async with httpx.AsyncClient(timeout=30.0) as client:
            tx_url = f"{self.BASE_URL}/users/{user_id}/exercise-transactions"

            try:
                tx_resp = await client.post(tx_url, headers=headers)
            except httpx.HTTPError:
                return SyncBatchResult(workouts=[], next_cursor=cursor, has_more=False)

            if tx_resp.status_code == 204:
                # 204 No Content: No new exercises available
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
                samples_data: dict[str, Any] = {"heart_rate": [], "coordinates": []}
                try:
                    samples_url = f"{ex_url}/samples"
                    samples_resp = await client.get(samples_url, headers=headers)
                    if samples_resp.status_code == 200:
                        raw_samples_resp = samples_resp.json()
                        sample_links = raw_samples_resp.get("samples")
                        if isinstance(sample_links, list):
                            for s_url in sample_links:
                                s_resp = await client.get(s_url, headers=headers)
                                if s_resp.status_code == 200:
                                    s_json = s_resp.json()
                                    stype = s_json.get("sample-type")
                                    r_rate = float(s_json.get("recording-rate", 1))
                                    s_data = s_json.get("data", "")
                                    if stype == 0:  # Heart rate
                                        if isinstance(s_data, str):
                                            bpm_list = [int(v.strip()) for v in s_data.split(",") if v.strip().isdigit()]
                                        elif isinstance(s_data, list):
                                            bpm_list = [int(v) for v in s_data if isinstance(v, (int, float))]
                                        else:
                                            bpm_list = []
                                        for idx, bpm in enumerate(bpm_list):
                                            samples_data["heart_rate"].append({
                                                "elapsed_sec": idx * r_rate,
                                                "bpm": bpm,
                                            })
                        elif isinstance(raw_samples_resp, dict) and ("heart_rate" in raw_samples_resp or "coordinates" in raw_samples_resp):
                            samples_data = raw_samples_resp
                except Exception:
                    pass

                workout = self.normalize_polar_exercise(ex_data, samples_data)
                normalized_workouts.append(workout)

            # Step 4: Commit transaction to mark exercises as processed
            await client.put(f"{tx_url}/{transaction_id}", headers=headers)

            return SyncBatchResult(
                workouts=normalized_workouts,
                next_cursor=cursor,
                has_more=False,
            )
