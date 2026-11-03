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
            at = page["meta"]["timestamp"][:19] + "Z"
            rows = {}
            for county in page["data"]["races"][0]["counties"]:
                results = county.get("results") or {}
                dem = results.get("bidenj", 0)
                rep = results.get("trumpd", 0)
                rows[county["fips"]] = [dem, rep, sum(results.values()) - dem - rep]
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
        now, then = turnout_by(counties, st, 2018), turnout_by(counties, st, 2016)
        a = sum(v for code, v in now.items() if code in then)
        b = sum(then[code] for code in now if code in then)
        ratio = a / b if b > 0 else 0.75
        expected = {}
        for code, _, _, total in base:
            x, y = now.get(code), then.get(code)
            local = x / y if x is not None and y else ratio
            expected[code] = total * max(0.3, min(1.6, local))
        snaps = []
        for page in readable(folder):
            race = page["races"][0]
            side = {key: value["party"]["nyt_id"] for key, value in race["candidate_metadata"].items()}
            at = (race["top_reporting_unit"].get("provider_updated_at") or race["updated_at"])[:19] + "Z"
            rows = {}
            for unit in race["reporting_units"]:
                if unit["level"] != "county" or unit.get("fips_county") is None:
                    continue
                rows[unit["fips_state"] + unit["fips_county"]] = votes_of(unit, side)
            if not snaps or snaps[-1]["at"] != at:
                snaps.append({"at": at, "counties": rows})
        snaps.sort(key=lambda snap: snap["at"])
        out[f"{st}-{seat}"] = {
            "st": st,
            "seat": seat,
            "base": base,
            "expected": expected,
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
