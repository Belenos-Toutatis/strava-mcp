"""Reconstruct a GPX file from Strava activity streams (for merging split rides)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import gpxpy
import gpxpy.gpx

GPXTPX_NS = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"


def _streams_by_type(streams_payload) -> dict[str, list]:
    """Strava /streams returns either a dict keyed by stream type or a list of stream objects."""
    if isinstance(streams_payload, dict):
        return {k: v.get("data", []) for k, v in streams_payload.items() if isinstance(v, dict)}
    out: dict[str, list] = {}
    for item in streams_payload or []:
        t = item.get("type")
        if t:
            out[t] = item.get("data", [])
    return out


def _add_trackpoint_extension(point: gpxpy.gpx.GPXTrackPoint, hr=None, cad=None, temp=None, watts=None) -> None:
    if hr is None and cad is None and temp is None and watts is None:
        return
    import xml.etree.ElementTree as ET

    tpx = ET.Element(f"{{{GPXTPX_NS}}}TrackPointExtension")
    if hr is not None:
        ET.SubElement(tpx, f"{{{GPXTPX_NS}}}hr").text = str(int(hr))
    if cad is not None:
        ET.SubElement(tpx, f"{{{GPXTPX_NS}}}cad").text = str(int(cad))
    if temp is not None:
        ET.SubElement(tpx, f"{{{GPXTPX_NS}}}atemp").text = f"{float(temp):.1f}"
    point.extensions.append(tpx)
    if watts is not None:
        power = ET.Element("power")
        power.text = str(int(watts))
        point.extensions.append(power)


def build_merged_gpx(segments: list[dict], track_name: str) -> bytes:
    """Build a GPX byte payload from N activity segments.

    Each segment must contain:
      - start_date: ISO8601 UTC string (from /activities/{id})
      - streams: payload from /activities/{id}/streams
    """
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "strava-mcp"
    track = gpxpy.gpx.GPXTrack(name=track_name)
    gpx.tracks.append(track)
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)

    # Sort by start_date.
    def _parse(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

    segments_sorted = sorted(segments, key=lambda s: _parse(s["start_date"]))

    for seg in segments_sorted:
        start = _parse(seg["start_date"])
        streams = _streams_by_type(seg["streams"])
        times = streams.get("time", [])
        latlng = streams.get("latlng", [])
        alt = streams.get("altitude", [])
        hr = streams.get("heartrate", [])
        cad = streams.get("cadence", [])
        watts = streams.get("watts", [])
        temp = streams.get("temp", [])

        if not latlng:
            continue

        n = min(len(times) or len(latlng), len(latlng))
        for i in range(n):
            lat, lon = latlng[i]
            t_offset = times[i] if i < len(times) else i
            timestamp = start + timedelta(seconds=int(t_offset))
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=lat,
                longitude=lon,
                elevation=alt[i] if i < len(alt) else None,
                time=timestamp,
            )
            _add_trackpoint_extension(
                point,
                hr=hr[i] if i < len(hr) else None,
                cad=cad[i] if i < len(cad) else None,
                temp=temp[i] if i < len(temp) else None,
                watts=watts[i] if i < len(watts) else None,
            )
            segment.points.append(point)

    return gpx.to_xml().encode("utf-8")
