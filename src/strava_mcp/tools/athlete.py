"""MCP tools for the authenticated athlete (profile, stats, zones)."""

from __future__ import annotations

from typing import Any

from ..client import StravaClient


def register(mcp, client: StravaClient) -> None:
    @mcp.tool()
    async def get_athlete() -> dict[str, Any]:
        """Profil de l'athlète connecté (incluant bikes/shoes)."""
        return await client.get("/athlete")

    @mcp.tool()
    async def get_athlete_stats() -> dict[str, Any]:
        """Totaux et stats récents (recent_run/ride/swim_totals, ytd, all-time)."""
        me = await client.get("/athlete")
        return await client.get(f"/athletes/{me['id']}/stats")

    @mcp.tool()
    async def get_athlete_zones() -> dict[str, Any]:
        """Zones HR et puissance configurées sur Strava."""
        return await client.get("/athlete/zones")
