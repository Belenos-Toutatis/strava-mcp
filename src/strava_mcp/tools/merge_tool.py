"""MCP tools to detect and merge split activities."""

from __future__ import annotations

from typing import Any

from ..client import StravaClient
from ..merge import detect_split_activities as _detect
from ..merge import merge_activities as _merge


def register(mcp, client: StravaClient) -> None:
    @mcp.tool()
    async def detect_split_activities(
        window_minutes: int = 30,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """Détecter des activités consécutives de même sport_type susceptibles d'être les morceaux
        d'une seule sortie splittée.

        Args:
            window_minutes: écart max (en minutes) entre fin de la 1re et début de la 2e.
            per_page: nombre d'activités récentes à scanner.
        """
        return await _detect(client, window_minutes=window_minutes, per_page=per_page)

    @mcp.tool()
    async def merge_split_activities(
        activity_ids: list[int],
        new_name: str | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Reconstruire une sortie unique à partir d'activités splittées.

        Méthode : récupère les streams (GPS + HR + puissance + cadence + temp) de chaque
        activité, les concatène dans un GPX continu, l'uploade comme nouvelle activité.
        L'API Strava ne permettant pas la suppression, les originaux devront être supprimés
        manuellement via l'UI (les URLs sont retournées).

        Args:
            activity_ids: liste d'IDs (2 ou plus).
            new_name: titre de la nouvelle activité (défaut: titre de la 1re).
            dry_run: si True (défaut), simule sans uploader.
        """
        return await _merge(client, activity_ids, new_name=new_name, dry_run=dry_run)
