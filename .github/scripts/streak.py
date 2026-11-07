#!/usr/bin/env python3
"""Generate assets/streak.svg (total contributions, current streak, longest streak)
from the GitHub GraphQL API. Standard library only."""
import json, os, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "simbaig"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/streak.svg"
MOCK = os.environ.get("MOCK_DAYS")  # test only: path to JSON [[iso_date, count], ...]

API = "https://api.github.com/graphql"
Q_CREATED = "query($u:String!){user(login:$u){createdAt}}"
Q_YEAR = """query($u:String!,$from:DateTime!,$to:DateTime!){user(login:$u){
  contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""


def gql(query, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "streak-card"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch_days():
    if MOCK:
        return {date.fromisoformat(d): c for d, c in json.load(open(MOCK))}, date(2021, 5, 11)
    created = datetime.fromisoformat(gql(Q_CREATED, {"u": USER})["user"]["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days, start = {}, created
    while start < now:
        end = min(start.replace(year=start.year + 1) - timedelta(seconds=1), now)
        d = gql(Q_YEAR, {"u": USER, "from": start.isoformat(), "to": end.isoformat()})
        for w in d["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in w["contributionDays"]:
                days[date.fromisoformat(day["date"])] = day["contributionCount"]
        start = end + timedelta(seconds=1)
    return days, created.date()


def stats(days):
    ordered = sorted(days)
    total = sum(days.values())
    # longest streak
    best = (0, None, None); run = 0; run_start = None
    prev = None
    for d in ordered:
        if days[d] > 0:
            if run and prev is not None and (d - prev).days == 1:
                run += 1
            else:
                run, run_start = 1, d
            if run > best[0]:
                best = (run, run_start, d)
        else:
            run = 0
        prev = d
    # current streak: ends on last day, or the day before if the last day is still empty
    last = ordered[-1]
    end = last if days[last] > 0 else last - timedelta(days=1)
    cur, d = 0, end
    while days.get(d, 0) > 0:
        cur += 1; d -= timedelta(days=1)
    cur_range = (d + timedelta(days=1), end) if cur else None
    return total, cur, cur_range, best


def fmt(d): return f"{d:%b} {d.day}, {d.year}" if d else ""
def fmt_short(d): return f"{d:%b} {d.day}"


def render(total, cur, cur_range, best, since, last):
    bg, line, num, lab, sub, ring, flame = "#141321", "#a9fef7", "#fe428e", "#fe428e", "#a9fef7", "#fe428e", "#f8d847"
    cur_dates = f"{fmt_short(cur_range[0])} - {fmt_short(cur_range[1])}" if cur_range else "No active streak"
    long_dates = f"{fmt(best[1])} - {fmt(best[2])}" if best[0] else "-"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 200" width="900" height="200" role="img" aria-label="GitHub streak: {total} contributions, current streak {cur} days, longest streak {best[0]} days">
  <style>
    text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif }}
    .num {{ font-size: 40px; font-weight: 700; fill: {num} }}
    .lab {{ font-size: 18px; fill: {lab} }}
    .sub {{ font-size: 14px; fill: {sub} }}
    .cur {{ fill: {flame}; font-weight: 700 }}
    @keyframes pop {{ from {{ opacity: 0; transform: translateY(6px) }} to {{ opacity: 1; transform: none }} }}
    .a {{ animation: pop .6s ease-out both }}
    .a2 {{ animation: pop .6s ease-out .15s both }}
    .a3 {{ animation: pop .6s ease-out .3s both }}
  </style>
  <rect width="900" height="200" rx="8" fill="{bg}"/>
  <line x1="300" y1="35" x2="300" y2="165" stroke="{line}" stroke-opacity=".35"/>
  <line x1="600" y1="35" x2="600" y2="165" stroke="{line}" stroke-opacity=".35"/>
  <g class="a" text-anchor="middle">
    <text class="num" x="150" y="92">{total:,}</text>
    <text class="lab" x="150" y="126">Total Contributions</text>
    <text class="sub" x="150" y="152">{fmt(since)} - Present</text>
  </g>
  <g class="a2" text-anchor="middle">
    <circle cx="450" cy="82" r="44" fill="none" stroke="{ring}" stroke-width="6"/>
    <text class="num cur" x="450" y="96" style="font-size:36px">{cur}</text>
    <path d="M450 22c6 8 10 11 10 18a10 10 0 0 1-20 0c0-4 2-6 4-9 1 3 3 5 5 5 0-6 0-9 1-14z" fill="{flame}" transform="translate(0,-4)"/>
    <text class="lab cur" x="450" y="152">Current Streak</text>
    <text class="sub" x="450" y="176">{cur_dates}</text>
  </g>
  <g class="a3" text-anchor="middle">
    <text class="num" x="750" y="92">{best[0]}</text>
    <text class="lab" x="750" y="126">Longest Streak</text>
    <text class="sub" x="750" y="152">{long_dates}</text>
  </g>
</svg>
'''


def main():
    days, since = fetch_days()
    total, cur, cur_range, best = stats(days)
    svg = render(total, cur, cur_range, best, since, max(days))
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(svg)
    print(f"total={total} current={cur} longest={best[0]} -> {OUT}")


if __name__ == "__main__":
    main()
