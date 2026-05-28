# strava-mcp

Serveur MCP personnel pour brancher Claude sur ton compte Strava : coaching à partir des activités, conseils nutrition, modification d'activités (titre, sport, matériel), et reconstruction d'une sortie unique à partir d'activités splittées.

## Ce que ça expose

**Lecture**
- `list_activities`, `get_activity`, `get_activity_streams`, `get_activity_zones`, `get_activity_laps`
- `get_athlete`, `get_athlete_stats`, `get_athlete_zones`
- `list_gear`, `get_gear`

**Écriture**
- `update_activity` — name, sport_type, gear_id, description, commute, trainer, hide_from_home

**Fusion d'activités splittées**
- `detect_split_activities` — détecte les paires consécutives même sport, écart court
- `merge_split_activities` — reconstruit un GPX continu à partir des streams, l'uploade comme nouvelle activité

## Limites Strava à connaître

- L'API ne permet **pas** de supprimer une activité ni de fusionner nativement deux activités. Après `merge_split_activities`, tu dois supprimer manuellement les originaux via strava.com (les URLs sont retournées).
- Les exports `.fit` bruts ne sont pas accessibles : la sortie reconstruite contient GPS + HR + puissance + cadence + température, mais pas les laps/pauses du fichier original.
- Pas de gestion fine des composants (chaîne, pneus) côté API.

## Setup

### 1. Créer une application Strava

Va sur https://www.strava.com/settings/api et crée une appli :
- **Authorization Callback Domain** : `127.0.0.1`
- Récupère le `Client ID` et le `Client Secret`.

### 2. Configurer le projet

```bash
git clone https://github.com/<ton-user>/strava-mcp.git ~/strava-mcp
cd ~/strava-mcp
cp .env.example .env
# remplis STRAVA_CLIENT_ID et STRAVA_CLIENT_SECRET
uv sync   # ou: pip install -e .
```

### 3. Premier lancement (autorisation OAuth)

```bash
uv run python -m strava_mcp.server
```

Au premier démarrage, le navigateur s'ouvre sur Strava pour autoriser les scopes (`read`, `activity:read_all`, `activity:write`, `profile:read_all`). Les tokens sont stockés dans `~/.config/strava-mcp/tokens.json` (chmod 600). Le refresh est automatique.

### 4. Brancher sur Claude Code

```bash
claude mcp add strava -- uv --directory ~/strava-mcp run python -m strava_mcp.server
```

Ou via `~/.claude.json` (entrée `mcpServers`):
```json
{
  "mcpServers": {
    "strava": {
      "command": "uv",
      "args": ["--directory", "~/strava-mcp", "run", "python", "-m", "strava_mcp.server"]
    }
  }
}
```

## Exemples d'usage en chat

- *« Liste mes 10 dernières activités Strava. »*
- *« Analyse ma sortie d'hier et donne-moi un retour de coach. »*
- *« Que je mange ce soir vu la sortie que j'ai faite ce matin ? »*
- *« Renomme ma sortie de samedi en "Sortie cool avec Paul". »*
- *« Change le vélo utilisé sur cette activité pour mon gravel. »*
- *« Détecte les sorties splittées des 30 derniers jours. »*
- *« Fusionne les activités 1234 et 5678 en une seule, mets `dry_run=False` quand tu es sûr. »*
- *« Analyse ma charge sur les 4 dernières semaines et propose-moi un plan pour cette semaine. »*

## Sécurité

- `tokens.json` et `.env` sont gitignorés.
- Le rate-limit local (100/15min, 1000/jour) évite de saturer ton quota Strava.
- Les tools d'écriture sont marqués comme tels : Claude Code demandera ta confirmation à chaque appel.
