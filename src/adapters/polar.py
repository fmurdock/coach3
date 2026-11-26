"""Polar AccessLink API adapter for outdoor running and multi-sport workouts."""

import base64
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any
from defusedxml import ElementTree as DefusedET
import httpx

from src.adapters.base import (
    BaseIngestionAdapter,
    NormalizedGPSPoint,
    NormalizedHeartRateSample,
    NormalizedSplit,
    NormalizedWorkout,
    SyncBatchResult,
)
from src.core.config import settings
from src.core.http_client import request_with_retry
from src.core.logging import redact_secrets

logger = logging.getLogger(__name__)


def map_polar_sport_to_discipline(sport: str | None, detailed_sport: str | None = None) -> tuple[str, str]:
    """Map Polar sport strings to canonical Coach3 discipline and display label."""
    combined = f"{sport or ''} {detailed_sport or ''}".upper()
    if any(k in combined for k in ("ROWING", "INDOOR_ROWING")):
        return "indoor_row", "Row"
    if any(k in combined for k in ("CYCLING", "BIKING", "SPINNING", "INDOOR_CYCLING")):
        return "erg_bike", "Ride"
    if any(k in combined for k in ("STRENGTH", "WEIGHT", "CROSSFIT", "GYM", "CALISTHENICS")):
        return "strength", "Strength"
    if any(k in combined for k in ("RUN", "JOG", "TRAIL", "TREADMILL", "WALK", "HIK")) or not combined.strip():
        return "outdoor_run", "Run"
    logger.warning("Unmapped Polar sport '%s' ('%s'); falling back to outdoor_run", sport, detailed_sport)
    return "outdoor_run", "Workout"


def parse_gpx_points(gpx_xml: str, start_time_utc: datetime | None = None) -> list[dict[str, Any]]:
    """Safely parse GPX XML trackpoints using defusedxml into coordinate dicts."""
    if not gpx_xml or "<trkpt" not in gpx_xml:
        return []

    try:
        root = DefusedET.fromstring(gpx_xml)
    except Exception:
        return []

    points: list[dict[str, Any]] = []
    first_ts: datetime | None = None

    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag != "trkpt":
            continue
        lat_str = elem.attrib.get("lat")
        lon_str = elem.attrib.get("lon")
        if lat_str is None or lon_str is None:
            continue

        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            continue

        ele_val: float | None = None
        pt_ts: datetime | None = None
        for child in elem:
            ctag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if ctag == "ele" and child.text:
                try:
                    ele_val = float(child.text.strip())
                except ValueError:
                    pass
            elif ctag == "time" and child.text:
                try:
                    pt_ts = datetime.fromisoformat(child.text.strip().replace("Z", "+00:00"))
                    if pt_ts.tzinfo is None:
                        pt_ts = pt_ts.replace(tzinfo=timezone.utc)
                    pt_ts = pt_ts.astimezone(timezone.utc)
                except ValueError:
                    pass

        if first_ts is None and pt_ts is not None:
            first_ts = pt_ts

        base_ts = start_time_utc or first_ts
        if pt_ts is not None and base_ts is not None:
            elapsed = max(0.0, (pt_ts - base_ts).total_seconds())
        else:
            elapsed = float(len(points))

        points.append({
            "elapsed_sec": round(elapsed, 2),
            "latitude": lat,
            "longitude": lon,
            "altitude": ele_val,
        })

    return points


def compute_elevation_from_points(points: list[dict[str, Any]] | list[NormalizedGPSPoint]) -> tuple[float | None, float | None]:
    """Compute cumulative elevation gain and loss (meters) from GPS points with a 1m hysteresis filter."""
    eles: list[float] = []
    for pt in points:
        val = pt.altitude_m if isinstance(pt, NormalizedGPSPoint) else pt.get("altitude")
        if val is not None:
            eles.append(float(val))
    if len(eles) < 2:
        return None, None

    gain = 0.0
    loss = 0.0
    ref = eles[0]
    for e in eles[1:]:
        diff = e - ref
        if diff >= 1.0:
            gain += diff
            ref = e
        elif diff <= -1.0:
            loss += abs(diff)
            ref = e
    return round(gain, 1), round(loss, 1)


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
    TOKEN_URL = "https://polarremote.com/v2/oauth2/token"  # noqa: S105
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
            resp = await request_with_retry(client, "POST", self.TOKEN_URL, headers=headers, data=data)
            resp.raise_for_status()
            return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
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
            resp = await request_with_retry(client, "POST", self.TOKEN_URL, headers=headers, data=data)
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
                resp = await request_with_retry(client, "GET", url, headers=headers, max_attempts=2)
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
                "error": redact_secrets(str(exc)),
            }

    def normalize_polar_exercise(
        self,
        exercise_data: dict[str, Any],
        samples_data: dict[str, Any] | None = None,
        laps_data: list[dict[str, Any]] | None = None,
    ) -> NormalizedWorkout:
        """Map raw Polar exercise JSON to canonical NormalizedWorkout entity."""
        raw_id = exercise_data.get("id")
        if raw_id is None or str(raw_id).strip() == "":
            raise ValueError("Polar exercise payload missing required 'id' field.")
        ext_id = str(raw_id).strip()

        discipline, label = map_polar_sport_to_discipline(
            exercise_data.get("sport"),
            exercise_data.get("detailed-sport-info") or exercise_data.get("detailed_sport_info"),
        )
        device = exercise_data.get("device", "Polar Watch")
        title = f"Polar {label} - {device}"

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

        avg_pace = None
        if distance_m > 0 and duration_sec > 0:
            avg_pace = duration_sec / (distance_m / 1000.0)

        hr_info = exercise_data.get("heart-rate") or exercise_data.get("heart_rate") or {}
        avg_hr = hr_info.get("average")
        max_hr = hr_info.get("maximum")

        elevation_gain = exercise_data.get("ascent")
        elevation_loss = exercise_data.get("descent")
        calories = exercise_data.get("calories")

        hr_samples: list[NormalizedHeartRateSample] = []
        gps_points: list[NormalizedGPSPoint] = []
        exercise_summary = dict(exercise_data)

        if samples_data:
            hr_list = samples_data.get("heart_rate") or samples_data.get("heart-rate") or []
            for sample in hr_list:
                sec = float(sample.get("elapsed_sec", sample.get("elapsed-sec", 0)))
                bpm = int(sample.get("bpm", 0))
                hr_samples.append(
                    NormalizedHeartRateSample(
                        elapsed_sec=sec,
                        bpm=bpm,
                        timestamp_utc=start_time_utc + timedelta(seconds=sec),
                    )
                )

            if "speed" in samples_data and samples_data["speed"]:
                exercise_summary["speed_samples"] = samples_data["speed"]

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
                        timestamp_utc=start_time_utc + timedelta(seconds=sec),
                    )
                )

        splits: list[NormalizedSplit] = []
        raw_laps = laps_data or exercise_data.get("laps") or []
        for idx, lap in enumerate(raw_laps, start=1):
            lap_dur = parse_iso_duration(lap.get("duration", 0))
            lap_dist = float(lap.get("distance", 0.0))
            lap_pace = (lap_dur / (lap_dist / 1000.0)) if (lap_dist > 0 and lap_dur > 0) else None
            lap_hr = lap.get("heart_rate", {}).get("average") if isinstance(lap.get("heart_rate"), dict) else lap.get("heart_rate")
            splits.append(
                NormalizedSplit(
                    split_index=idx,
                    distance_m=lap_dist,
                    duration_sec=lap_dur,
                    split_type="interval",
                    avg_pace_sec_per_km=lap_pace,
                    avg_heart_rate=int(lap_hr) if lap_hr else None,
                )
            )

        if (elevation_gain is None or elevation_loss is None) and gps_points:
            calc_gain, calc_loss = compute_elevation_from_points(gps_points)
            if elevation_gain is None:
                elevation_gain = calc_gain
            if elevation_loss is None:
                elevation_loss = calc_loss

        return NormalizedWorkout(
            provider="polar",
            external_id=ext_id,
            discipline=discipline,
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
            raw_summary=exercise_summary,
            heart_rate_samples=hr_samples,
            gps_route_points=gps_points,
            splits=splits,
        )

    async def register_user(self, access_token: str, member_id: str) -> dict[str, Any] | None:
        """Register a user with Polar AccessLink API (required once after OAuth authorization)."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await request_with_retry(
                client,
                "POST",
                f"{self.BASE_URL}/users",
                headers=headers,
                json={"member-id": member_id},
            )
            if resp.status_code in (200, 201, 409):
                return resp.json() if resp.status_code in (200, 201) else None
            resp.raise_for_status()
            return resp.json()

    async def commit_batch(
        self,
        access_token: str,
        commit_token: dict[str, Any],
    ) -> None:
        """Commit a Polar AccessLink exercise transaction ONLY after local DB persistence succeeds."""
        tx_url = commit_token.get("tx_url")
        transaction_id = commit_token.get("transaction_id")
        if not tx_url or not transaction_id:
            return
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await request_with_retry(client, "PUT", f"{tx_url}/{transaction_id}", headers=headers)
            resp.raise_for_status()

    async def fetch_workouts_batch(
        self,
        access_token: str,
        cursor: dict[str, Any] | None = None,
        since: datetime | None = None,
    ) -> SyncBatchResult:
        """Pull new workouts and telemetry from Polar AccessLink without prematurely committing."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        user_id = (cursor.get("user_id") if cursor else None) or "me"

        async with httpx.AsyncClient(timeout=30.0) as client:
            tx_url = f"{self.BASE_URL}/users/{user_id}/exercise-transactions"

            tx_resp = await request_with_retry(client, "POST", tx_url, headers=headers)
            if tx_resp.status_code == 204:
                return SyncBatchResult(workouts=[], next_cursor=cursor, has_more=False)

            tx_resp.raise_for_status()
            tx_data = tx_resp.json()
            transaction_id = tx_data.get("transaction-id")
            if not transaction_id:
                return SyncBatchResult(workouts=[], next_cursor=cursor, has_more=False)

            exercises_resp = await request_with_retry(
                client,
                "GET",
                f"{tx_url}/{transaction_id}",
                headers=headers,
            )
            exercises_resp.raise_for_status()
            exercise_urls: list[str] = exercises_resp.json().get("exercises", [])

            normalized_workouts: list[NormalizedWorkout] = []

            for ex_url in exercise_urls:
                ex_resp = await request_with_retry(client, "GET", ex_url, headers=headers)
                if ex_resp.status_code != 200:
                    continue
                ex_data = ex_resp.json()

                samples_data: dict[str, Any] = {"heart_rate": [], "coordinates": [], "speed": []}
                try:
                    samples_resp = await request_with_retry(client, "GET", f"{ex_url}/samples", headers=headers, max_attempts=2)
                    if samples_resp.status_code == 200:
                        raw_samples_resp = samples_resp.json()
                        sample_links = raw_samples_resp.get("samples")
                        if isinstance(sample_links, list):
                            for s_url in sample_links:
                                s_resp = await request_with_retry(client, "GET", s_url, headers=headers, max_attempts=2)
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
                                    elif stype == 1:  # Speed in km/h
                                        if isinstance(s_data, str):
                                            spd_list = [float(v.strip()) for v in s_data.split(",") if v.strip().replace(".", "", 1).isdigit()]
                                        elif isinstance(s_data, list):
                                            spd_list = [float(v) for v in s_data if isinstance(v, (int, float))]
                                        else:
                                            spd_list = []
                                        for idx, spd in enumerate(spd_list):
                                            sec = idx * r_rate
                                            pace = (3600.0 / spd) if spd > 0.5 else None
                                            samples_data["speed"].append({
                                                "elapsed_sec": sec,
                                                "speed_kmh": spd,
                                                "pace_sec": pace,
                                            })
                        elif isinstance(raw_samples_resp, dict):
                            for k, v in raw_samples_resp.items():
                                samples_data[k] = v
                except Exception as exc:
                    logger.warning("Optional Polar samples fetch failed for %s: %s", ex_url, type(exc).__name__)

                if not samples_data["coordinates"]:
                    try:
                        gpx_headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Accept": "application/gpx+xml",
                        }
                        gpx_resp = await request_with_retry(client, "GET", f"{ex_url}/gpx", headers=gpx_headers, max_attempts=2)
                        if gpx_resp.status_code == 200 and "<trkpt" in gpx_resp.text:
                            start_str = ex_data.get("start-time") or ex_data.get("start_time")
                            off_min = ex_data.get("start-time-utc-offset")
                            parsed_start = None
                            if start_str:
                                try:
                                    if "Z" in start_str or "+" in start_str or (len(start_str) > 19 and "-" in start_str[19:]):
                                        parsed_start = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)
                                    elif off_min is not None:
                                        parsed_start = datetime.fromisoformat(start_str).replace(tzinfo=timezone(timedelta(minutes=int(off_min)))).astimezone(timezone.utc)
                                except Exception:
                                    parsed_start = None
                            samples_data["coordinates"] = parse_gpx_points(gpx_resp.text, start_time_utc=parsed_start)
                    except Exception as exc:
                        logger.warning("Optional Polar GPX fetch failed: %s", type(exc).__name__)

                if not samples_data["coordinates"]:
                    try:
                        coord_resp = await request_with_retry(client, "GET", f"{ex_url}/coordinates", headers=headers, max_attempts=2)
                        if coord_resp.status_code == 200:
                            c_json = coord_resp.json()
                            c_list = c_json.get("coordinates") if isinstance(c_json, dict) else c_json
                            if isinstance(c_list, list):
                                samples_data["coordinates"] = c_list
                    except Exception as exc:
                        logger.debug("Optional Polar coordinates fetch skipped: %s", type(exc).__name__)

                try:
                    hz_resp = await request_with_retry(client, "GET", f"{ex_url}/heart-rate-zones", headers=headers, max_attempts=2)
                    if hz_resp.status_code == 200:
                        hz_json = hz_resp.json()
                        if isinstance(hz_json, dict) and hz_json.get("zone"):
                            ex_data["polar_zones"] = hz_json["zone"]
                except Exception as exc:
                    logger.debug("Optional Polar HR zones fetch skipped: %s", type(exc).__name__)

                laps_data = None
                try:
                    laps_resp = await request_with_retry(client, "GET", f"{ex_url}/laps", headers=headers, max_attempts=2)
                    if laps_resp.status_code == 200:
                        l_json = laps_resp.json()
                        laps_data = l_json.get("laps") if isinstance(l_json, dict) else l_json
                except Exception as exc:
                    logger.debug("Optional Polar laps fetch skipped: %s", type(exc).__name__)

                try:
                    workout = self.normalize_polar_exercise(ex_data, samples_data, laps_data=laps_data)
                    normalized_workouts.append(workout)
                except ValueError as val_exc:
                    logger.warning("Skipping malformed Polar exercise: %s", val_exc)

            # Defer remote transaction PUT commit until sync_service confirms durable DB commit!
            return SyncBatchResult(
                workouts=normalized_workouts,
                next_cursor=cursor,
                has_more=False,
                pending_commit_token={
                    "tx_url": tx_url,
                    "transaction_id": transaction_id,
                },
            )
