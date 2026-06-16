#!/usr/bin/env python3
"""Generate docs/world_cup_2026.ics from ESPN's public FIFA World Cup feeds.

Stdlib only. Iterates each day of the tournament, calls ESPN's scoreboard for
that date, and (for live or finished matches) calls ESPN's match summary to
pull goal scorers, assists, and cards. Writes one VEVENT per match.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ICS_PATH = ROOT / "docs" / "world_cup_2026.ics"
CACHE_DIR = ROOT / "cache"
ASSIST_CACHE = CACHE_DIR / "assists.json"

TOURNAMENT_START = dt.date(2026, 6, 11)
TOURNAMENT_END = dt.date(2026, 7, 19)
HARD_STOP = dt.date(2026, 7, 20)

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={date}"
)
SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}"
)

UA = "Mozilla/5.0 (world-cup-2026-calendar; +https://github.com/)"
TIMEOUT = 20

# FIFA / ESPN 3-letter codes -> flag emoji. Generous superset of plausible
# qualifiers; unknown codes fall back to ⚽.
FLAGS: dict[str, str] = {
    "USA": "🇺🇸", "CAN": "🇨🇦", "MEX": "🇲🇽",
    "ARG": "🇦🇷", "BRA": "🇧🇷", "URU": "🇺🇾", "COL": "🇨🇴", "ECU": "🇪🇨",
    "PAR": "🇵🇾", "CHI": "🇨🇱", "PER": "🇵🇪", "VEN": "🇻🇪", "BOL": "🇧🇴",
    "ENG": "🏴\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
    "SCO": "🏴\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "WAL": "🏴\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
    "NIR": "🇬🇧",
    "FRA": "🇫🇷", "GER": "🇩🇪", "ESP": "🇪🇸", "POR": "🇵🇹", "NED": "🇳🇱",
    "ITA": "🇮🇹", "BEL": "🇧🇪", "CRO": "🇭🇷", "SUI": "🇨🇭", "DEN": "🇩🇰",
    "POL": "🇵🇱", "SRB": "🇷🇸", "CZE": "🇨🇿", "AUT": "🇦🇹", "TUR": "🇹🇷",
    "NOR": "🇳🇴", "SWE": "🇸🇪", "UKR": "🇺🇦", "HUN": "🇭🇺", "ROU": "🇷🇴",
    "GRE": "🇬🇷", "IRL": "🇮🇪", "SVK": "🇸🇰", "SVN": "🇸🇮", "FIN": "🇫🇮",
    "ALB": "🇦🇱", "BUL": "🇧🇬", "ISL": "🇮🇸",
    "MAR": "🇲🇦", "SEN": "🇸🇳", "EGY": "🇪🇬", "NGA": "🇳🇬", "GHA": "🇬🇭",
    "CIV": "🇨🇮", "ALG": "🇩🇿", "TUN": "🇹🇳", "CMR": "🇨🇲", "MLI": "🇲🇱",
    "RSA": "🇿🇦", "ANG": "🇦🇴", "BFA": "🇧🇫", "CPV": "🇨🇻",
    "JPN": "🇯🇵", "KOR": "🇰🇷", "IRN": "🇮🇷", "AUS": "🇦🇺", "KSA": "🇸🇦",
    "IRQ": "🇮🇶", "UAE": "🇦🇪", "QAT": "🇶🇦", "UZB": "🇺🇿", "JOR": "🇯🇴",
    "CHN": "🇨🇳", "THA": "🇹🇭",
    "CRC": "🇨🇷", "JAM": "🇯🇲", "PAN": "🇵🇦", "HON": "🇭🇳", "SLV": "🇸🇻",
    "HAI": "🇭🇹", "TRI": "🇹🇹", "CUB": "🇨🇺", "CUR": "🇨🇼",
    "NZL": "🇳🇿",
    "BIH": "🇧🇦", "RUS": "🇷🇺", "ISR": "🇮🇱", "GEO": "🇬🇪", "ARM": "🇦🇲",
    "AZE": "🇦🇿", "MNE": "🇲🇪", "MKD": "🇲🇰", "KAZ": "🇰🇿", "BLR": "🇧🇾",
    "LUX": "🇱🇺", "CYP": "🇨🇾", "MLT": "🇲🇹", "MDA": "🇲🇩",
    "GUI": "🇬🇳", "GAM": "🇬🇲", "ZAM": "🇿🇲", "ZIM": "🇿🇼", "MOZ": "🇲🇿",
    "MAD": "🇲🇬", "BEN": "🇧🇯", "TOG": "🇹🇬", "CGO": "🇨🇬", "COD": "🇨🇩",
    "GAB": "🇬🇦", "UGA": "🇺🇬", "KEN": "🇰🇪", "TAN": "🇹🇿", "ETH": "🇪🇹",
    "SUD": "🇸🇩", "LBY": "🇱🇾", "MTN": "🇲🇷", "NIG": "🇳🇪", "SLE": "🇸🇱",
    "LBR": "🇱🇷", "GNB": "🇬🇼", "BDI": "🇧🇮", "RWA": "🇷🇼", "COM": "🇰🇲",
    "BHR": "🇧🇭", "OMA": "🇴🇲", "KUW": "🇰🇼", "YEM": "🇾🇪", "LIB": "🇱🇧",
    "SYR": "🇸🇾", "PLE": "🇵🇸", "AFG": "🇦🇫", "IND": "🇮🇳", "PAK": "🇵🇰",
    "BAN": "🇧🇩", "VIE": "🇻🇳", "MAS": "🇲🇾", "SIN": "🇸🇬", "INA": "🇮🇩",
    "PHI": "🇵🇭", "MYA": "🇲🇲", "PRK": "🇰🇵", "TPE": "🇹🇼", "HKG": "🇭🇰",
    "MAC": "🇲🇴", "TKM": "🇹🇲", "TJK": "🇹🇯", "KGZ": "🇰🇬",
    "GUA": "🇬🇹", "NCA": "🇳🇮", "BLZ": "🇧🇿", "DOM": "🇩🇴", "BAH": "🇧🇸",
    "BRB": "🇧🇧", "GRN": "🇬🇩", "GUY": "🇬🇾", "SUR": "🇸🇷",
    "FIJ": "🇫🇯", "PNG": "🇵🇬", "SOL": "🇸🇧", "VAN": "🇻🇺", "TAH": "🇵🇫",
    "NCL": "🇳🇨", "SAM": "🇼🇸", "TGA": "🇹🇴",
}


def fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as e:
        print(f"  fetch failed: {url}: {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"  json decode failed: {url}: {e}", file=sys.stderr)
        return None


def flag(abbr: str) -> str:
    return FLAGS.get((abbr or "").upper(), "⚽")


def parse_iso_utc(s: str) -> dt.datetime:
    # ESPN uses e.g. "2026-06-11T20:00Z"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def collect_events() -> list[dict]:
    events: list[dict] = []
    seen: set[str] = set()
    day = TOURNAMENT_START
    while day <= TOURNAMENT_END:
        url = SCOREBOARD_URL.format(date=day.strftime("%Y%m%d"))
        data = fetch_json(url)
        if data and "events" in data:
            for ev in data["events"]:
                eid = str(ev.get("id", ""))
                if eid and eid not in seen:
                    seen.add(eid)
                    events.append(ev)
        day += dt.timedelta(days=1)
    return events


def extract_match(ev: dict) -> dict | None:
    try:
        comp = ev["competitions"][0]
        competitors = comp["competitors"]
        home = next(c for c in competitors if c.get("homeAway") == "home")
        away = next(c for c in competitors if c.get("homeAway") == "away")
    except (KeyError, IndexError, StopIteration):
        return None

    def team_info(c: dict) -> dict:
        team = c.get("team", {}) or {}
        return {
            "name": team.get("displayName") or team.get("name") or team.get("shortDisplayName") or "TBD",
            "abbr": team.get("abbreviation", ""),
            "score": c.get("score", "0"),
        }

    status = comp.get("status", {}) or ev.get("status", {}) or {}
    stype = status.get("type", {}) or {}
    venue = (comp.get("venue") or {}).get("fullName") or ""
    city_parts = []
    addr = (comp.get("venue") or {}).get("address") or {}
    if addr.get("city"):
        city_parts.append(addr["city"])
    if addr.get("state"):
        city_parts.append(addr["state"])
    if addr.get("country"):
        city_parts.append(addr["country"])
    location = ", ".join([p for p in [venue] + city_parts if p])

    return {
        "id": str(ev.get("id", "")),
        "date": ev.get("date") or comp.get("date"),
        "home": team_info(home),
        "away": team_info(away),
        "home_id": str(home.get("id", "")),
        "away_id": str(away.get("id", "")),
        "state": stype.get("state", "pre"),  # "pre" | "in" | "post"
        "detail": stype.get("shortDetail") or stype.get("detail") or "",
        "clock": status.get("displayClock", ""),
        "completed": bool(stype.get("completed")),
        "location": location,
        "link": ev.get("links", [{}])[0].get("href", "") if ev.get("links") else "",
        "name": ev.get("name") or comp.get("name") or "",
    }


def _participant_name(p: dict) -> str:
    ath = p.get("athlete") if isinstance(p, dict) and "athlete" in p else p
    return (ath or {}).get("displayName") or (ath or {}).get("shortName") or ""


def _parse_assist_from_text(text: str) -> str:
    """ESPN goal text looks like '...Assisted by John Doe.' or 'Assisted by John Doe with a header.'"""
    low = text.lower()
    if "assisted by" not in low:
        return ""
    idx = low.index("assisted by") + len("assisted by")
    tail = text[idx:].lstrip(" :")
    # cut at sentence-ending punctuation / connectors
    for stop in [".", " with ", " following ", " after "]:
        i = tail.lower().find(stop)
        if i >= 0:
            tail = tail[:i]
    return tail.strip(" .,:")


def fetch_match_details(event_id: str, cache: dict) -> dict:
    """Return {goals: [(team_abbr, scorer, assist, minute)], cards: [(team_abbr, player, color, minute)]}.

    For finished matches we cache the result so we don't refetch unchanged data.
    """
    cached = cache.get(event_id)
    if cached and cached.get("final"):
        return cached["data"]

    data = fetch_json(SUMMARY_URL.format(event_id=event_id))
    if not data:
        return cached["data"] if cached else {"goals": [], "cards": []}

    goals: list[tuple[str, str, str, str]] = []
    cards: list[tuple[str, str, str, str]] = []

    # Build map: team_id -> abbreviation (header competitors carries the abbr)
    team_abbr: dict[str, str] = {}
    for c in ((data.get("header") or {}).get("competitions") or [{}])[0].get("competitors", []) or []:
        t = c.get("team", {}) or {}
        if t.get("id"):
            team_abbr[str(t["id"])] = t.get("abbreviation", "")
    for grp in (data.get("boxscore") or {}).get("teams", []) or []:
        t = grp.get("team", {}) or {}
        if t.get("id"):
            team_abbr.setdefault(str(t["id"]), t.get("abbreviation", ""))

    for ev in data.get("keyEvents") or []:
        etype = (ev.get("type") or {}).get("type", "") or (ev.get("type") or {}).get("text", "")
        etype_l = etype.lower()
        clock = (ev.get("clock") or {}).get("displayValue") or ""
        team_id = str(((ev.get("team") or {}).get("id") or ""))
        tabbr = team_abbr.get(team_id, "")
        text = ev.get("text") or ev.get("shortText") or ""
        participants = ev.get("participants") or ev.get("athletesInvolved") or []

        if "goal" in etype_l or ev.get("scoringPlay"):
            scorer = _participant_name(participants[0]) if participants else ""
            assist = _participant_name(participants[1]) if len(participants) > 1 else ""
            if not scorer and text:
                # "Goal! ... Player Name (Team) ..." — best-effort
                short = ev.get("shortText") or ""
                if short.endswith(" Goal"):
                    scorer = short[:-5].strip()
            if not assist:
                assist = _parse_assist_from_text(text)
            if scorer:
                goals.append((tabbr, scorer, assist, clock))
            continue

        if "card" in etype_l:
            color = "🟥" if "red" in etype_l else "🟨"
            player = _participant_name(participants[0]) if participants else ""
            if not player:
                short = ev.get("shortText") or ""
                # "Player Name Yellow Card"
                for suf in (" Yellow Card", " Red Card", " Second Yellow card"):
                    if short.endswith(suf):
                        player = short[: -len(suf)].strip()
                        break
            if player:
                cards.append((tabbr, player, color, clock))

    result = {"goals": goals, "cards": cards}
    completed = bool(((data.get("header") or {}).get("competitions") or [{}])[0]
                     .get("status", {}).get("type", {}).get("completed"))
    cache[event_id] = {"final": completed, "data": result}
    return result


# -------- ICS writers --------

def ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\n", "\\n"))


def fold_lines(lines: list[str]) -> str:
    out: list[str] = []
    for line in lines:
        # iCalendar octet-based folding at 75 octets, continuation lines start with a space
        b = line.encode("utf-8")
        if len(b) <= 75:
            out.append(line)
            continue
        # split on octet boundaries that don't break a UTF-8 char
        chunks: list[bytes] = []
        i = 0
        first = True
        while i < len(b):
            limit = 75 if first else 74  # leave room for leading space on continuation
            end = min(len(b), i + limit)
            # back up to not split a UTF-8 multibyte sequence
            while end < len(b) and (b[end] & 0xC0) == 0x80:
                end -= 1
            chunks.append(b[i:end])
            i = end
            first = False
        joined = chunks[0].decode("utf-8")
        for c in chunks[1:]:
            joined += "\r\n " + c.decode("utf-8")
        out.append(joined)
    return "\r\n".join(out) + "\r\n"


def fmt_utc(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_summary(m: dict) -> str:
    h, a = m["home"], m["away"]
    hf, af = flag(h["abbr"]), flag(a["abbr"])
    if m["state"] == "in":
        clock = m["clock"] or m["detail"] or "LIVE"
        return f"🔴 {hf} {h['name']} {h['score']}-{a['score']} {a['name']} {af} ({clock})"
    if m["state"] == "post" or m["completed"]:
        return f"{hf} {h['name']} {h['score']}-{a['score']} {a['name']} {af} (FT)"
    return f"{hf} {h['name']} vs {a['name']} {af}"


def build_description(m: dict, details: dict) -> str:
    lines: list[str] = []
    if m["state"] != "pre":
        lines.append(f"Score: {m['home']['score']}-{m['away']['score']}")
    if m["detail"]:
        lines.append(f"Status: {m['detail']}")
    if details.get("goals"):
        lines.append("")
        lines.append("Goals:")
        for tabbr, scorer, assist, minute in details["goals"]:
            tag = flag(tabbr) if tabbr else "⚽"
            mn = f" {minute}" if minute else ""
            a = f" (assist: {assist})" if assist else ""
            lines.append(f"  ⚽{mn} {tag} {scorer}{a}")
    if details.get("cards"):
        lines.append("")
        lines.append("Cards:")
        for tabbr, player, color, minute in details["cards"]:
            tag = flag(tabbr) if tabbr else ""
            mn = f" {minute}" if minute else ""
            lines.append(f"  {color}{mn} {tag} {player}")
    if m["link"]:
        lines.append("")
        lines.append(m["link"])
    return "\n".join(lines).strip()


def build_vevent(m: dict, details: dict, now_utc: dt.datetime) -> list[str]:
    start = parse_iso_utc(m["date"])
    end = start + dt.timedelta(hours=2)
    uid = f"espn-{m['id']}@world-cup-2026"
    summary = build_summary(m)
    desc = build_description(m, details)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{fmt_utc(now_utc)}",
        f"DTSTART:{fmt_utc(start)}",
        f"DTEND:{fmt_utc(end)}",
        f"SUMMARY:{ics_escape(summary)}",
    ]
    if m["location"]:
        lines.append(f"LOCATION:{ics_escape(m['location'])}")
    if desc:
        lines.append(f"DESCRIPTION:{ics_escape(desc)}")
    if m["link"]:
        lines.append(f"URL:{m['link']}")
    lines.append("STATUS:CONFIRMED")
    lines.append("END:VEVENT")
    return lines


def build_calendar(matches: list[dict], details_by_id: dict[str, dict]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    head = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//world-cup-2026-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:FIFA World Cup 2026",
        "X-WR-CALDESC:Auto-updating scores, goals, assists, and cards for the 2026 FIFA World Cup.",
        "REFRESH-INTERVAL;VALUE=DURATION:PT15M",
        "X-PUBLISHED-TTL:PT15M",
    ]
    body: list[str] = []
    for m in sorted(matches, key=lambda x: x["date"] or ""):
        details = details_by_id.get(m["id"], {"goals": [], "cards": []})
        body.extend(build_vevent(m, details, now))
    tail = ["END:VCALENDAR"]
    return fold_lines(head + body + tail)


def load_cache() -> dict:
    if ASSIST_CACHE.exists():
        try:
            return json.loads(ASSIST_CACHE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ASSIST_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def main() -> int:
    today = dt.date.today()
    if today >= HARD_STOP:
        print(f"Past tournament window ({today} >= {HARD_STOP}); nothing to do.")
        return 0

    print(f"Fetching ESPN scoreboards {TOURNAMENT_START} -> {TOURNAMENT_END} ...")
    raw_events = collect_events()
    matches = [m for m in (extract_match(e) for e in raw_events) if m and m.get("date")]
    print(f"Got {len(matches)} ESPN events.")

    if not matches:
        # Don't blow away an existing good file
        if ICS_PATH.exists():
            print("0 ESPN events; keeping previous ICS untouched.")
            return 0
        print("0 ESPN events and no prior ICS; writing empty calendar shell.")
        ICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ICS_PATH.write_text(fold_lines([
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//world-cup-2026-calendar//EN",
            "END:VCALENDAR",
        ]))
        return 0

    cache = load_cache()
    details_by_id: dict[str, dict] = {}
    n_final = n_live = 0
    for m in matches:
        if m["state"] == "post" or m["completed"]:
            n_final += 1
        elif m["state"] == "in":
            n_live += 1
        if m["state"] in ("in", "post") or m["completed"]:
            details_by_id[m["id"]] = fetch_match_details(m["id"], cache)

    ics = build_calendar(matches, details_by_id)

    ICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    old = ICS_PATH.read_text() if ICS_PATH.exists() else ""
    # Strip DTSTAMP lines before comparing so we don't churn every run
    def strip_dtstamp(s: str) -> str:
        return "\r\n".join(l for l in s.split("\r\n") if not l.startswith("DTSTAMP:"))
    if strip_dtstamp(old) == strip_dtstamp(ics):
        print(f"No changes ({len(matches)} matches; {n_final} final, {n_live} live).")
    else:
        ICS_PATH.write_text(ics)
        print(f"Wrote {ICS_PATH}: {len(matches)} matches ({n_final} final, {n_live} live).")

    save_cache(cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
