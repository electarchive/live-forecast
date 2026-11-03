import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALPHA = 0.2
EPS = 1e-3
CHANCE = 0.995
COUNTED = 0.5
TIERED = ((CHANCE, COUNTED), (0.99999, 0.2))
STAGES = ((0, 0.5), (0.5, 0.8), (0.8, 0.95), (0.95, 9))
DRAWS = 2000
SEED = 20261103
GROUPS = {
    "2020": lambda row: row["set"] == "2020",
    "2022": lambda row: row["set"] == "2022",
    "real": lambda row: row["set"] in ("2020", "2022"),
    "midterm": lambda row: row["set"] == "midterm",
    "presidential": lambda row: row["set"] == "presidential",
    "simulated": lambda row: row["set"] in ("midterm", "presidential"),
    "close": lambda row: row["set"] in ("midterm", "presidential") and abs(row["truth"]) < 0.1,
    "holdout": lambda row: row["set"] == "holdout",
    "holdout2020": lambda row: row["race"].startswith("holdout/2020-"),
    "holdout2022": lambda row: row["race"].startswith("holdout/2022-"),
    "holdout2024": lambda row: row["race"].startswith("holdout/2024-"),
    "holdoutClose": lambda row: row["set"] == "holdout" and abs(row["truth"]) < 0.1,
    "2026": lambda row: row["set"] == "2026",
    "2026late": lambda row: row["set"] == "2026" and row["minutes"] >= 1440,
}


def load(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    return [row for row in rows if row["status"] == "estimating"]


def wis(y: float, lo: float, mid: float, hi: float) -> float:
    interval = (hi - lo) + (2 / ALPHA) * max(0.0, lo - y) + (2 / ALPHA) * max(0.0, y - hi)
    return (0.5 * abs(y - mid) + (ALPHA / 2) * interval) / 1.5


def terms(row: dict) -> dict[str, float]:
    won = 1.0 if row["truth"] > 0 else 0.0
    p = row["pD"]
    q = min(1 - EPS, max(EPS, p))
    return {
        "brier": (p - won) ** 2,
        "log": -(won * math.log(q) + (1 - won) * math.log(1 - q)),
        "wis": 100 * wis(row["truth"], row["lo"], row["mid"], row["hi"]),
        "cover80": 1.0 if row["lo"] <= row["truth"] <= row["hi"] else 0.0,
        "mae": 100 * abs(row["mid"] - row["truth"]),
        "turnout": 100 * abs(row["tmid"] / row["total"] - 1),
        "tcover80": 1.0 if row["tlo"] <= row["total"] <= row["thi"] else 0.0,
        "wrong95": 1.0 if max(p, 1 - p) >= 0.95 and (p >= 0.5) != (won == 1.0) else 0.0,
    }


def metrics(rows: list[dict]) -> dict:
    if not rows:
        return {}
    sums: dict[str, float] = defaultdict(float)
    for row in rows:
        for key, value in terms(row).items():
            sums[key] += value
    out = {"n": len(rows)} | {key: value / len(rows) for key, value in sums.items()}
    out["wrong95"] = int(sums["wrong95"])
    return out


def intervals(rows: list[dict]) -> dict[str, list[float]]:
    races: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        race = races[row["race"]]
        race["n"] += 1
        for key, value in terms(row).items():
            race[key] += value
    totals = list(races.values())
    keys = ("brier", "log", "wis", "cover80", "mae", "turnout", "tcover80")
    random.seed(SEED)
    found: dict[str, list[float]] = {key: [] for key in keys}
    for _ in range(DRAWS):
        picked = random.choices(totals, k=len(totals))
        n = sum(race["n"] for race in picked)
        for key in keys:
            found[key].append(sum(race[key] for race in picked) / n)
    out = {}
    for key, values in found.items():
        values.sort()
        out[key] = [values[int(0.05 * DRAWS)], values[int(0.95 * DRAWS) - 1]]
    return out


def ready(row: dict, rule: tuple[tuple[float, float], ...]) -> bool:
    p = row["pD"]
    return any(min(row["sin"], 1) >= counted and max(p, 1 - p) >= chance for chance, counted in rule)


def calls(rows: list[dict], chance: float = CHANCE, rule: tuple[tuple[float, float], ...] | None = None) -> dict:
    races: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        races[row["race"]].append(row)
    called = wrong = flips = 0
    shares: list[float] = []
    for race in races.values():
        race.sort(key=lambda row: (row["share"], row["at"]))
        won = race[0]["truth"] > 0
        side = None
        for row in race:
            leads = row["pD"] >= 0.5
            if side is not None and leads != side:
                flips += 1
            side = leads
        for row in race:
            p = row["pD"]
            if ready(row, rule or ((chance, COUNTED),)):
                called += 1
                shares.append(row["share"])
                if (p >= 0.5) != won:
                    wrong += 1
                break
    total = len(races)
    return {
        "races": total,
        "called": called,
        "falseCalls": wrong,
        "callShare": sum(shares) / len(shares) if shares else None,
        "flips": flips / max(total, 1),
    }


def reliability(rows: list[dict]) -> list[list[float]]:
    edges = (0, 0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98, 1.0001)
    out = []
    for low, high in zip(edges, edges[1:], strict=False):
        found = [row for row in rows if low <= row["pD"] < high]
        if found:
            out.append(
                [
                    sum(row["pD"] for row in found) / len(found),
                    sum(1 for row in found if row["truth"] > 0) / len(found),
                    len(found),
                ]
            )
    return out


def report(rows: list[dict]) -> dict:
    table = reliability(rows)
    n = sum(count for _, _, count in table)
    return (
        metrics(rows)
        | calls(rows)
        | {
            "ece": sum(count * abs(p - o) for p, o, count in table) / max(n, 1),
            "calls99": calls(rows, 0.99),
            "tiered": calls(rows, rule=TIERED),
            "intervals": intervals(rows),
            "reliability": table,
            "stages": {
                f"{low}-{high}": metrics([row for row in rows if low <= row["share"] < high]) for low, high in STAGES
            },
        }
    )


def show(results: dict[str, dict]) -> None:
    keys = ("n", "races", "brier", "log", "wis", "cover80", "mae", "turnout", "tcover80", "ece", "wrong95", "called", "falseCalls", "flips")
    print("metric".ljust(11) + "".join(name.rjust(13) for name in results))
    for key in keys:
        line = key.ljust(11)
        for entry in results.values():
            value = entry.get(key)
            line += (f"{value:13.4f}" if isinstance(value, float) else f"{value:13d}") if value is not None else " " * 13
        print(line)
    for key in ("brier", "log", "wis", "cover80"):
        line = f"{key} 90%".ljust(11)
        for entry in results.values():
            low, high = entry["intervals"][key]
            line += f"{low:.3f}-{high:.3f}".rjust(13)
        print(line)


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs/estimates.jsonl"
    rows = load(source)
    results = {name: report(found) for name, keep in GROUPS.items() if (found := [row for row in rows if keep(row)])}
    show(results)
    source.with_name("scores.json").write_text(json.dumps(results, indent=1) + "\n")
