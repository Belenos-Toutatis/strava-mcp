"""MCP tools for gear (bikes, shoes)."""

from __future__ import annotations

from typing import Any

from ..client import StravaClient


def register(mcp, client: StravaClient) -> None:
    @mcp.tool()
    async def list_gear() -> dict[str, list[dict[str, Any]]]:
        """Lister bikes et shoes attachés au compte (depuis /athlete)."""
        me = await client.get("/athlete")
        return {
            "bikes": me.get("bikes", []) or [],
            "shoes": me.get("shoes", []) or [],
        }

    @mcp.tool()
    async def get_gear(gear_id: str) -> dict[str, Any]:
        """Détail d'un équipement (km cumulés, marque, modèle)."""
        return await client.get(f"/gear/{gear_id}")
