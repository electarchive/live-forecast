import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score import DRAWS, GROUPS, ROOT, SEED, calls, metrics, reliability, terms

KEYS = ("brier", "log", "wis", "cover80", "mae", "turnout")
STRICT = (0.995, 0.999, 0.9999, 0.99999, 0.999999, 0.9999999)


def read(path: Path) -> dict[tuple[str, str, float], dict]:
    rows = (json.loads(line) for line in path.read_text().splitlines() if line)
    return {(row["race"], row["at"], row["share"]): row for row in rows if row["status"] == "estimating"}


def paired(model: list[dict], baseline: list[dict]) -> dict[str, dict[str, float]]:
    races: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for ours, theirs in zip(model, baseline, strict=True):
        race = races[ours["race"]]
        race["n"] += 1
        mine, other = terms(ours), terms(theirs)
        for key in KEYS:
            race[key] += other[key] - mine[key]
    totals = list(races.values())
    random.seed(SEED)
    found: dict[str, list[float]] = {key: [] for key in KEYS}
    for _ in range(DRAWS):
        picked = random.choices(totals, k=len(totals))
        n = sum(race["n"] for race in picked)
        for key in KEYS:
            found[key].append(sum(race[key] for race in picked) / n)
    n = sum(race["n"] for race in totals)
    out = {}
    for key, values in found.items():
        values.sort()
        out[key] = {
            "gap": sum(race[key] for race in totals) / n,
            "low": values[int(0.05 * DRAWS)],
            "high": values[int(0.95 * DRAWS) - 1],
            "modelBetter": sum(1 for value in values if value > 0) / DRAWS,
        }
    return out


def summary(rows: list[dict]) -> dict:
    table = reliability(rows)
    n = sum(count for _, _, count in table)
    return metrics(rows) | calls(rows) | {"ece": sum(count * abs(p - o) for p, o, count in table) / max(n, 1)}


def strict(rows: list[dict]) -> dict[str, dict]:
    return {str(chance): calls(rows, chance) for chance in STRICT}


def compare(model: dict[tuple[str, str, float], dict], path: Path) -> dict:
    baseline = read(path)
    shared = sorted(key for key in model if key in baseline)
    results = {}
    for name, keep in GROUPS.items():
        ours = [model[key] for key in shared if keep(model[key])]
        theirs = [baseline[key] for key in shared if keep(model[key])]
        if ours:
            results[name] = {
                "model": summary(ours),
                "baseline": summary(theirs),
                "gap": paired(ours, theirs),
                "strict": strict(theirs),
            }
    return results


def show(label: str, results: dict) -> None:
    print(label)
    print("group".ljust(13) + "".join(key.rjust(24) for key in ("brier", "log", "wis", "cover80", "wrong95", "called/wrong")))
    for name, entry in results.items():
        for side in ("model", "baseline"):
            found = entry[side]
            line = f"{name} {side[0]}".ljust(13)
            line += "".join(f"{found[key]:24.4f}" for key in ("brier", "log", "wis", "cover80"))
            line += f"{found['wrong95']:24d}" + f"{found['called']}/{found['falseCalls']}".rjust(24)
            print(line)
        line = f"{name} gap".ljust(13)
        for key in ("brier", "log", "wis", "cover80"):
            gap = entry["gap"][key]
            line += f"{gap['gap']:+.4f} [{gap['low']:+.3f},{gap['high']:+.3f}]".rjust(24)
        print(line)
        line = f"{name} strict".ljust(13)
        line += "".join(f"{chance}:{found['called']}/{found['falseCalls']}".rjust(18) for chance, found in entry["strict"].items())
        print(line)


if __name__ == "__main__":
    model = read(ROOT / "outputs/estimates.jsonl")
    paths = [Path(arg) for arg in sys.argv[1:]] or [ROOT / "outputs/baseline-narrow.jsonl", ROOT / "outputs/baseline-wide.jsonl"]
    for path in paths:
        results = compare(model, path)
        show(path.stem, results)
        path.with_name(path.stem.replace("baseline", "comparison") + ".json").write_text(json.dumps(results, indent=1) + "\n")
