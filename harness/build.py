import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATES = {
    "arizona": "az",
    "georgia": "ga",
    "nevada": "nv",
    "north-carolina": "nc",
    "ohio": "oh",
    "pennsylvania": "pa",
    "wisconsin": "wi",
}
SKIPPED = ("ak", "dc", "pr")


def rows_for(counties: dict, st: str, year: int, seat: str) -> list | None:
    for key, rows in counties.items():
        parts = key.split("/")
        if parts[1] == st and parts[2].startswith(f"{year}-") and parts[2].endswith("-general") and parts[3] == seat:
            return rows
    return None


def turnout_by(counties: dict, st: str, year: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, rows in counties.items():
        parts = key.split("/")
        if parts[1] != st or not (parts[2].startswith(f"{year}-") and parts[2].endswith("-general")):
            continue
        if parts[3].startswith("house"):
            continue
        for code, _, _, total in rows:
            out[code] = max(out.get(code, 0), total)
    return out


def truth(rows: list) -> dict:
    d = sum(row[1] for row in rows)
    r = sum(row[2] for row in rows)
    t = sum(row[3] for row in rows)
    return {"margin": (d - r) / t, "total": t}


def readable(folder: Path) -> list[dict]:
    out = []
    for path in sorted(folder.glob("*.json")):
        try:
            out.append(json.loads(path.read_text()))
        except ValueError:
            continue
    return out


def night2020(counties: dict) -> dict:
    out = {}
    for folder in sorted((ROOT / "frames/raw/2020").iterdir()):
        st = folder.name
        snaps: dict[str, dict] = {}
        for page in readable(folder):
            at, rows = page2020(page)
            snaps[at] = {"counties": rows}
        out[st] = {
            "base": counties[f"us/{st}/2016-11-08-general/president"],
            "snaps": [{"at": at, **snap} for at, snap in sorted(snaps.items())],
            "truth": truth(counties[f"us/{st}/2020-11-03-general/president"]),
        }
    return out


def votes_of(unit: dict, side: dict) -> list[int]:
    d = r = o = 0
    for candidate in unit["candidates"]:
        votes = candidate["votes"]["total"]
        party = side.get(candidate["nyt_id"])
        if party == "DEM":
            d += votes
        elif party == "GOP":
            r += votes
        else:
            o += votes
    return [d, r, o]


def expected_for(counties: dict, st: str, base: list) -> dict[str, float]:
    now, then = turnout_by(counties, st, 2018), turnout_by(counties, st, 2016)
    a = sum(v for code, v in now.items() if code in then)
    b = sum(then[code] for code in now if code in then)
    ratio = a / b if b > 0 else 0.75
    expected = {}
    for code, _, _, total in base:
        x, y = now.get(code), then.get(code)
        local = x / y if x is not None and y else ratio
        expected[code] = total * max(0.3, min(1.6, local))
    return expected


def page2020(page: dict) -> tuple[str, dict[str, list[int]]]:
    race = page["data"]["races"][0]
    side = {candidate["candidate_key"]: candidate["party_id"] for candidate in race["candidates"]}
    rows = {}
    for county in race["counties"]:
        results = county.get("results") or {}
        dem = sum(votes for key, votes in results.items() if side.get(key) == "democrat")
        rep = sum(votes for key, votes in results.items() if side.get(key) == "republican")
        rows[county["fips"]] = [dem, rep, sum(results.values()) - dem - rep]
    return page["meta"]["timestamp"][:19] + "Z", rows


def page2022(page: dict) -> tuple[str, dict[str, list[int]]]:
    race = page["races"][0]
    side = {key: value["party"]["nyt_id"] for key, value in race["candidate_metadata"].items()}
    at = (race["top_reporting_unit"].get("provider_updated_at") or race["updated_at"])[:19] + "Z"
    rows = {}
    for unit in race["reporting_units"]:
        if unit["level"] != "county" or unit.get("fips_county") is None:
            continue
        rows[unit["fips_state"] + unit["fips_county"]] = votes_of(unit, side)
    return at, rows


def holdout(counties: dict, manifest: dict) -> dict:
    out = {}
    for key, entry in manifest.get("holdout", {}).items():
        year, st, seat = entry["year"], entry["state"], entry["seat"]
        final = rows_for(counties, st, year, seat)
        base = rows_for(counties, st, 2016 if year == 2020 else 2020, "president")
        reason = None
        if st in SKIPPED:
            reason = "state left out"
        elif final is None or base is None:
            reason = "no certified county results"
        else:
            d, r, t = (sum(row[i] for row in final) for i in (1, 2, 3))
            if d < 0.2 * t or r < 0.2 * t or d + r < 0.75 * t or len(final) < 3:
                reason = "not a two-party race in at least 3 counties"
        if reason is not None:
            print("holdout", key, "left out:", reason)
            continue
        ids = {row[0] for row in base}
        snaps = []
        for page in readable(ROOT / "frames/raw/holdout" / key):
            at, rows = page2020(page) if year == 2020 else page2022(page)
            if not snaps or snaps[-1]["at"] != at:
                snaps.append({"at": at, "counties": rows})
        snaps.sort(key=lambda snap: snap["at"])
        units = {fips for snap in snaps for fips in snap["counties"]}
        target = truth(final)
        counted = [sum(sum(votes) for votes in snap["counties"].values()) / target["total"] for snap in snaps]
        if not units <= ids:
            reason = f"{len(units - ids)} page units are not baseline counties"
        elif any(share > 1.02 for share in counted):
            reason = "page counts exceed the certified total"
        elif sum(1 for share in counted if share >= 0.05) < 3:
            reason = "fewer than 3 checkpoints"
        if reason is not None:
            print("holdout", key, "left out:", reason)
            continue
        out[key] = {
            "year": year,
            "st": st,
            "seat": seat,
            "base": base,
            **({"expected": expected_for(counties, st, base)} if year == 2022 else {}),
            "snaps": snaps,
            "truth": target,
        }
        print("holdout", key, len(snaps), "snapshots", f"final margin {target['margin']:+.4f}", f"units {len(units)}/{len(ids)}")
    return out


def night2022(counties: dict) -> dict:
    out = {}
    for folder in sorted((ROOT / "frames/raw/2022").iterdir()):
        name = folder.name
        seat = "senate" if name.endswith("us-senate") else "governor"
        st = STATES[name.removesuffix("-us-senate").removesuffix("-governor")]
        final = rows_for(counties, st, 2022, seat)
        base = rows_for(counties, st, 2020, "president")
        if final is None or base is None:
            continue
        snaps = []
        for page in readable(folder):
            at, rows = page2022(page)
            if not snaps or snaps[-1]["at"] != at:
                snaps.append({"at": at, "counties": rows})
        snaps.sort(key=lambda snap: snap["at"])
        out[f"{st}-{seat}"] = {
            "st": st,
            "seat": seat,
            "base": base,
            "expected": expected_for(counties, st, base),
            "snaps": snaps,
            "truth": truth(final),
        }
    return out


if __name__ == "__main__":
    counties = json.loads((ROOT / "inputs/counties.json").read_text())
    for year, build in ((2020, night2020), (2022, night2022)):
        night = build(counties)
        (ROOT / f"frames/{year}.json").write_text(json.dumps(night))
        for key, entry in night.items():
            print(year, key, len(entry["snaps"]), "snapshots", f"final margin {entry['truth']['margin']:+.4f}")
    manifest = json.loads((ROOT / "frames/manifest.json").read_text())
    if (ROOT / "frames/raw/holdout").exists():
        (ROOT / "frames/holdout.json").write_text(json.dumps(holdout(counties, manifest)))
