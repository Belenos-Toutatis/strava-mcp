# strava-mcp

MCP server for [Strava](https://www.strava.com/) — full API coverage for activities, segments, routes, clubs, gear, and split activity merging.

Built with Python + [FastMCP](https://github.com/jlowin/fastmcp). Works with Claude Desktop, Claude Code, and any MCP-compatible client.

## Features

### Read
- **Activities** — list, detail, streams (HR, GPS, power, cadence, altitude...), zones, laps
- **Athlete** — profile, stats (YTD, all-time, recent), HR/power zones
- **Segments** — detail, explore by area, starred segments, efforts, streams
- **Routes** — list, detail, streams, export GPX/TCX
- **Clubs** — list, detail, members, activities, admins
- **Gear** — list bikes/shoes, detail (km, brand, model)
- **Social** — comments and kudos on activities

### Write
- **Update activity** — rename, change sport type, assign gear, mark commute/trainer, edit description
- **Merge split activities** — detect and recombine activities that were accidentally split into multiple recordings (rebuilds a GPX from streams and uploads it)

### 31 tools total

## Setup

### 1. Create a Strava API app

Go to https://www.strava.com/settings/api and create an application.

### 2. Configure credentials

```bash
cd strava-mcp
cp .env.example .env
# Edit .env with your STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET
```

### 3. Install and run

```bash
# With uv (recommended)
uv sync
uv run python -m strava_mcp.server

# First run opens your browser for OAuth authorization
```

### 4. Add to Claude Desktop

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "strava": {
      "command": "uv",
      "args": ["--directory", "/path/to/strava-mcp", "run", "python", "-m", "strava_mcp.server"]
    }
  }
}
```

## Authentication

OAuth 2.0 with loopback redirect on `http://127.0.0.1:8731/callback`. Tokens are persisted in `~/.config/strava-mcp/tokens.json` and refreshed automatically.

## Rate limits

Built-in rate limiter: 100 requests / 15 min, 1000 / day (Strava defaults). Automatic back-off on 429 responses.

## Logging

JSON-lines logs in `~/.config/strava-mcp/logs/strava-mcp.log` (5 x 1 MB rotation). Set `STRAVA_MCP_LOG_LEVEL=DEBUG` in `.env` for verbose output.

## API changes (June 2026)

Strava announced API changes effective June 2027:
- Base URL migrating from `www.strava.com/api/v3` to `www.api-v3.strava.com`
- Auth tokens must be sent in headers (already the case in this implementation)

## License

MIT
