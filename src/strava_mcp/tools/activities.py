"""MCP tools to read and update Strava activities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..client import StravaClient


def _to_epoch(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(
            datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
        )
    except ValueError as e:
        raise ValueError(f"Date ISO8601 invalide: {iso!r}") from e


def register(mcp, client: StravaClient) -> None:
    @mcp.tool()
    async def list_activities(
        after: str | None = None,
        before: str | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Lister tes activités Strava.

        Args:
            after: borne basse, date ISO8601 (ex: '2026-05-01T00:00:00Z').
            before: borne haute, date ISO8601.
            per_page: nb max d'activités (défaut 30, max 200).
            page: pagination (1-indexée).
        """
        return await client.get(
            "/athlete/activities",
            after=_to_epoch(after),
            before=_to_epoch(before),
            per_page=min(per_page, 200),
            page=page,
        )

    @mcp.tool()
    async def get_activity(activity_id: int, include_all_efforts: bool = False) -> dict[str, Any]:
        """Détail complet d'une activité (incluant segments, splits, gear, kilojoules)."""
        return await client.get(
            f"/activities/{activity_id}",
            include_all_efforts=str(include_all_efforts).lower(),
        )

    @mcp.tool()
    async def get_activity_streams(
        activity_id: int,
        keys: str = "time,distance,heartrate,watts,altitude,velocity_smooth,cadence,temp,latlng",
    ) -> dict[str, Any]:
        """Séries temporelles d'une activité (HR, puissance, vitesse, altitude, GPS, etc.).

        Args:
            activity_id: ID de l'activité.
            keys: types de streams séparés par virgule. Par défaut tous les utiles.
        """
        return await client.get(
            f"/activities/{activity_id}/streams",
            keys=keys,
            key_by_type="true",
        )

    @mcp.tool()
    async def get_activity_zones(activity_id: int) -> list[dict[str, Any]]:
        """Temps passé par zone HR / puissance pour une activité."""
        return await client.get(f"/activities/{activity_id}/zones")

    @mcp.tool()
    async def get_activity_laps(activity_id: int) -> list[dict[str, Any]]:
        """Tours / laps d'une activité."""
        return await client.get(f"/activities/{activity_id}/laps")

    @mcp.tool()
    async def update_activity(
        activity_id: int,
        name: str | None = None,
        sport_type: str | None = None,
        gear_id: str | None = None,
        description: str | None = None,
        commute: bool | None = None,
        trainer: bool | None = None,
        hide_from_home: bool | None = None,
    ) -> dict[str, Any]:
        """Mettre à jour une activité existante.

        Args:
            activity_id: ID de l'activité.
            name: nouveau titre.
            sport_type: valeur Strava (ex: 'Ride', 'Run', 'GravelRide', 'MountainBikeRide',
                'VirtualRide', 'TrailRun', 'Walk', 'Hike', 'Swim'...). Préfère ce champ à 'type'.
            gear_id: ID du matériel (vélo ou chaussures). Voir list_gear().
            description: nouvelle description.
            commute: marquer comme trajet domicile-travail.
            trainer: marquer comme home trainer / indoor.
            hide_from_home: masquer du flux d'accueil.
        """
        return await client.put(
            f"/activities/{activity_id}",
            name=name,
            sport_type=sport_type,
            gear_id=gear_id,
            description=description,
            commute=commute,
            trainer=trainer,
            hide_from_home=hide_from_home,
        )
