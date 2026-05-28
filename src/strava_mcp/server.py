"""FastMCP entrypoint for the Strava connector."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .client import StravaClient
from .tools import (
    register_activities,
    register_athlete,
    register_gear,
    register_merge,
)

mcp = FastMCP("strava-mcp")
_client = StravaClient()

register_activities(mcp, _client)
register_athlete(mcp, _client)
register_gear(mcp, _client)
register_merge(mcp, _client)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
