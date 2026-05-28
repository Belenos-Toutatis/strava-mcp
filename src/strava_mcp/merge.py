"""Merge split Strava activities by rebuilding a GPX from their streams and uploading."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from .client import StravaClient, StravaError
from .streams import build_merged_gpx

STREAM_KEYS = "time,latlng,altitude,heartrate,cadence,watts,temp"


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


async def _fetch_segment(client: StravaClient, activity_id: int) -> dict:
    activity = await client.get(f"/activities/{activity_id}")
    streams = await client.get(
        f"/activities/{activity_id}/streams",
        keys=STREAM_KEYS,
        key_by_type="true",
    )
    return {
        "id": activity_id,
        "name": activity.get("name"),
        "sport_type": activity.get("sport_type") or activity.get("type"),
        "start_date": activity["start_date"],
        "distance": activity.get("distance"),
        "moving_time": activity.get("moving_time"),
        "url": f"https://www.strava.com/activities/{activity_id}",
        "streams": streams,
    }


async def merge_activities(
    client: StravaClient,
    activity_ids: list[int],
    new_name: str | None = None,
    dry_run: bool = True,
) -> dict:
    if len(activity_ids) < 2:
        raise ValueError("Il faut au moins 2 IDs d'activité à fusionner.")

    segments = await asyncio.gather(*[_fetch_segment(client, aid) for aid in activity_ids])
    segments.sort(key=lambda s: _parse_iso(s["start_date"]))

    sport_types = {s["sport_type"] for s in segments}
    if len(sport_types) > 1:
        raise ValueError(
            f"Les activités ont des sport_type différents: {sport_types}. Fusion refusée."
        )

    track_name = new_name or segments[0]["name"] or "Sortie fusionnée"
    summary = {
        "segments": [
            {
                "id": s["id"],
                "name": s["name"],
                "start_date": s["start_date"],
                "distance_m": s["distance"],
                "moving_time_s": s["moving_time"],
                "url": s["url"],
            }
            for s in segments
        ],
        "new_name": track_name,
        "sport_type": segments[0]["sport_type"],
        "dry_run": dry_run,
    }

    if dry_run:
        summary["next_step"] = (
            "Relance avec dry_run=False pour uploader la sortie fusionnée. "
            "Tu devras ensuite supprimer manuellement les originaux via l'UI Strava."
        )
        return summary

    gpx_bytes = build_merged_gpx(segments, track_name)
    files = {"file": (f"merge-{segments[0]['id']}.gpx", gpx_bytes, "application/gpx+xml")}
    data = {
        "name": track_name,
        "data_type": "gpx",
        "external_id": "strava-mcp-merge-" + "-".join(str(s["id"]) for s in segments),
    }
    upload = await client.post_form("/uploads", data=data, files=files)
    upload_id = upload.get("id")
    if not upload_id:
        raise StravaError(500, f"Upload sans ID: {upload}")

    # Poll status until activity_id or error.
    new_activity_id = None
    for _ in range(60):
        await asyncio.sleep(2)
        status = await client.get(f"/uploads/{upload_id}")
        if status.get("error"):
            raise StravaError(500, f"Upload Strava échoué: {status['error']}")
        if status.get("activity_id"):
            new_activity_id = status["activity_id"]
            break

    if not new_activity_id:
        summary["upload_id"] = upload_id
        summary["status"] = "pending"
        summary["note"] = "Strava traite encore l'upload. Réinterroge /uploads/{upload_id}."
        return summary

    summary["new_activity_id"] = new_activity_id
    summary["new_activity_url"] = f"https://www.strava.com/activities/{new_activity_id}"
    summary["manual_delete_urls"] = [s["url"] for s in segments]
    summary["note"] = (
        "Nouvelle activité créée. Supprime les originales via les URLs ci-dessus "
        "(l'API Strava ne permet pas la suppression)."
    )
    return summary


async def detect_split_activities(
    client: StravaClient,
    window_minutes: int = 30,
    per_page: int = 30,
) -> list[dict]:
    """Heuristic: find consecutive activities with same sport_type within a small time gap."""
    acts = await client.get("/athlete/activities", per_page=per_page)
    acts = sorted(acts, key=lambda a: _parse_iso(a["start_date"]))
    candidates: list[dict] = []
    for prev, curr in zip(acts, acts[1:]):
        if (prev.get("sport_type") or prev.get("type")) != (
            curr.get("sport_type") or curr.get("type")
        ):
            continue
        prev_end = _parse_iso(prev["start_date"]).timestamp() + (prev.get("elapsed_time") or 0)
        curr_start = _parse_iso(curr["start_date"]).timestamp()
        gap_min = (curr_start - prev_end) / 60
        if 0 <= gap_min <= window_minutes:
            candidates.append(
                {
                    "gap_minutes": round(gap_min, 1),
                    "sport_type": prev.get("sport_type") or prev.get("type"),
                    "first": {
                        "id": prev["id"],
                        "name": prev["name"],
                        "start_date": prev["start_date"],
                        "distance_m": prev.get("distance"),
                        "elapsed_time_s": prev.get("elapsed_time"),
                    },
                    "second": {
                        "id": curr["id"],
                        "name": curr["name"],
                        "start_date": curr["start_date"],
                        "distance_m": curr.get("distance"),
                        "elapsed_time_s": curr.get("elapsed_time"),
                    },
                }
            )
    return candidates
