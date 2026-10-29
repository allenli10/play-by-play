import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = “https://site.api.espn.com/apis/site/v2/sports/basketball/nba”
TEAM = “tor”
OUTPUT_DIR = Path(“data/raw/espn”)

SESSION = requests.Session()
SESSION.headers.update({
“User-Agent”: “NBA-PlayByPlay-Research/1.0”
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
competitions = event.get(“competitions”, [])

if competitions:
    status = competitions[0].get("status", {})
else:
    status = event.get("status", {})
return status.get("type", {}).get("completed", False)

def get_recent_games():
url = f”{BASE_URL}/teams/{TEAM}/schedule”
schedule = get_json(url)

events = schedule.get("events", [])
completed = [
    event for event in events
    if is_completed(event)
]
completed.sort(
    key=lambda event: event.get("date", ""),
    reverse=True
)
return completed[:5]

def collect_game(event):
game_id = str(event[“id”])

url = f"{BASE_URL}/summary?event={game_id}"
summary = get_json(url)
plays = summary.get("plays", [])
if not plays:
    raise ValueError(
        f"No play-by-play returned for game {game_id}"
    )
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
output_file = OUTPUT_DIR / f"{game_id}.json"
with output_file.open("w", encoding="utf-8") as file:
    json.dump(
        summary,
        file,
        indent=2,
        ensure_ascii=False
    )
competition = (
    event.get("competitions", [{}])[0]
)
competitors = competition.get("competitors", [])
print(
    f"Saved {game_id}: "
    f"{event.get('name', 'Unknown matchup')} "
    f"({len(plays)} plays)"
)
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
    "collected_at": datetime.now(
        timezone.utc
    ).isoformat()
}

def main():
print(“Starting Raptors data collection…”)

games = get_recent_games()
if len(games) < 5:
    print(
        f"Warning: Only {len(games)} "
        "completed games found."
    )
if not games:
    raise RuntimeError("No completed Raptors games found.")
results = []
for event in games:
    results.append(collect_game(event))
    time.sleep(1)
index = {
    "team": "Toronto Raptors",
    "team_abbreviation": "TOR",
    "collected_at": datetime.now(
        timezone.utc
    ).isoformat(),
    "game_count": len(results),
    "games": results
}
Path("data").mkdir(exist_ok=True)
with open(
    "data/index.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        index,
        file,
        indent=2,
        ensure_ascii=False
    )
print(
    f"Collection complete: "
    f"{len(results)} games saved."
)

if name == “main”:
main()