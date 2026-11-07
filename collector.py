import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
TEAM = "TOR"
TEAM_ID = "28"
OUTPUT_DIR = Path("data/raw/espn")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "NBA-PlayByPlay-Research/1.0"
})


def get_json(url, retries=3):
    for attempt in range(retries):
        try:
            response = SESSION.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def is_completed(event):
    competitions = event.get("competitions", [])

    if competitions:
        status = competitions[0].get("status", {})
    else:
        status = event.get("status", {})
    return status.get("type", {}).get("completed", False)


def includes_raptors(event):
    """Return whether the event's competition includes Toronto."""
    for competition in event.get("competitions", []):
        for competitor in competition.get("competitors", []):
            team = competitor.get("team", {})
            if str(team.get("id", "")) == TEAM_ID or team.get("abbreviation") == TEAM:
                return True
    return False


def get_recent_games(limit=10):
    # The scoreboard's default date window can contain no finished games
    # (especially on off-days). Scan recent dates so the collector can still
    # find Toronto's latest completed games.
    events_by_id = {}
    today = datetime.now(timezone.utc).date()
    for days_ago in range(7):
        date = (today - __import__("datetime").timedelta(days=days_ago)).strftime("%Y%m%d")
        scoreboard = get_json(f"{BASE_URL}/scoreboard?dates={date}")
        for event in scoreboard.get("events", []):
            if is_completed(event) and includes_raptors(event):
                events_by_id[event.get("id")] = event

    completed = list(events_by_id.values())
    completed.sort(key=lambda event: event.get("date", ""), reverse=True)
    return completed[:limit]


def collect_game(event):
    game_id = str(event["id"])
    url = f"{BASE_URL}/summary?event={game_id}"
    summary = get_json(url)
    plays = summary.get("plays", [])
    if not plays:
        raise ValueError(f"No play-by-play returned for game {game_id}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{game_id}.json"
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])
    print(f"Saved {game_id}: {event.get('name', 'Unknown matchup')} ({len(plays)} plays)")
    return {
        "game_id": game_id,
        "date": event.get("date"),
        "name": event.get("name"),
        "short_name": event.get("shortName"),
        "status": "completed",
        "play_count": len(plays),
        "source": "ESPN",
        "file": str(output_file),
        "competitors": competitors,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    print(f"Starting {TEAM} data collection...")

    games = get_recent_games()
    if not games:
        raise RuntimeError(f"No completed {TEAM} games found in the last 7 days.")

    results = []
    for event in games:
        results.append(collect_game(event))
        time.sleep(1)

    index = {
        "team": "Toronto Raptors",
        "team_abbreviation": TEAM,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "game_count": len(results),
        "games": results,
    }

    Path("data").mkdir(exist_ok=True)
    with open("data/index.json", "w", encoding="utf-8") as file:
        json.dump(index, file, indent=2, ensure_ascii=False)

    print(f"Collection complete: {len(results)} games saved.")


if __name__ == "__main__":
    main()
