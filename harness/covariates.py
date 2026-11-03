import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "inputs/sources"

if __name__ == "__main__":
    education: dict[str, dict[str, float]] = {"2012": {}, "2019": {}}
    with (SOURCES / "education.csv").open(encoding="latin-1") as handle:
        for row in csv.DictReader(handle):
            fips = row["FIPS Code"].zfill(5)
            if row["Attribute"] == "Percent of adults with a bachelor's degree or higher, 2008-12":
                education["2012"][fips] = float(row["Value"]) / 100
            elif row["Attribute"] == "Percent of adults with a bachelor's degree or higher, 2019-23":
                education["2019"][fips] = float(row["Value"]) / 100
    land: dict[str, float] = {}
    for name in ("2020_Gaz_counties_national.txt", "2022_Gaz_counties_national.txt"):
        with (SOURCES / name).open(encoding="latin-1") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                row = {key.strip(): value.strip() for key, value in row.items()}
                land[row["GEOID"]] = float(row["ALAND_SQMI"])
    people: dict[str, dict[str, tuple[float, float, float, float]]] = {"2012": {}, "2019": {}}
    with (SOURCES / "cc-est2019-alldata.csv").open(encoding="latin-1") as handle:
        for row in csv.DictReader(handle):
            if row["AGEGRP"] != "0" or row["YEAR"] not in ("5", "12"):
                continue
            total = float(row["TOT_POP"])
            share = lambda key, row=row, total=total: (float(row[key + "_MALE"]) + float(row[key + "_FEMALE"])) / total
            people["2012" if row["YEAR"] == "5" else "2019"][row["STATE"] + row["COUNTY"]] = (
                total,
                share("NHWA"),
                share("NHBA"),
                share("H"),
            )
    out: dict[str, dict[str, list[float]]] = {}
    for vintage in ("2012", "2019"):
        found = {}
        for fips, (total, white, black, hispanic) in people[vintage].items():
            college = education[vintage].get(fips)
            area = land.get(fips)
            if college is None or area is None or area <= 0:
                continue
            found[fips] = [round(college, 4), round(white, 4), round(black, 4), round(hispanic, 4), round(math.log(total / area), 3)]
        out[vintage] = found
        print(vintage, len(found), "counties")
    (ROOT / "inputs/covariates.json").write_text(json.dumps(out))
