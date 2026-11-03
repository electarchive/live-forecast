# Live election-night forecast: replication files

This repository holds the paper, outputs, and code behind the backtest of the live election-night forecast on [electionsarchive.com](https://electionsarchive.com/live/methodology). On election night, the forecast estimates each race's final margin, its final turnout, and each candidate's chance of winning from county counts as they come in.

- [paper.md](paper.md) explains how the model works, how we tested it, and how it scored.
- The model itself is [`packages/analytics/src/live.ts`](https://github.com/electarchive/electionsarchive/blob/bb3e39cfdc52d30c2b005f1213b402c130f1a28b/packages/analytics/src/live.ts) in the main electionsarchive.com repository. This repository links to it at commit `bb3e39cfdc52d30c2b005f1213b402c130f1a28b` and does not copy it.
- The [methodology page](https://electionsarchive.com/live/methodology) explains the model for general readers.

## Contents

| Path | Contents |
|---|---|
| `paper.md` | The paper |
| `outputs/estimates.jsonl` | The model's estimate at every checkpoint of every replayed race (9,603 rows) |
| `outputs/scores.json` | The scores in the paper, written by `harness/score.py` |
| `outputs/ablations.json` | The ablation results in section 6 of the paper |
| `outputs/baseline-narrow.jsonl`, `outputs/baseline-wide.jsonl` | The estimates of the two versions of the regression nowcast in sections 7 and 8 of the paper, in the same format as `outputs/estimates.jsonl` (9,485 rows each) |
| `outputs/comparison-narrow.json`, `outputs/comparison-wide.json` | The comparisons in sections 7 and 8 of the paper, written by `harness/compare.py` |
| `figures/` | The paper's figures, drawn by `harness/figures.py` |
| `frames/manifest.json` | Every Internet Archive capture of The New York Times results pages used for the real nights, with its address and SHA-256 checksum. The held-out races in section 8 of the paper are under `holdout`. |
| `inputs/covariates.json` | County demographic shares, built from public Census Bureau and USDA Economic Research Service files |
| `harness/` | The scripts that download the captures, rebuild the counts, replay the races, and score them, along with `baseline.ts`, the regression nowcast from section 7 of the paper |

Each line of `outputs/estimates.jsonl` is one checkpoint:

| Field | Meaning |
|---|---|
| `set` | `2020` or `2022` for the real nights the model was tuned on, `holdout` for the held-out real nights, and `presidential` or `midterm` for simulated ones |
| `race` | The race |
| `at`, `minutes` | The time of the checkpoint, and minutes since the race's first update. Simulated nights run on a made-up clock that starts on January 1, 2030. |
| `share` | The share of the final vote counted at the checkpoint |
| `sin` | The model's estimate of the share counted |
| `status` | `estimating`, or `too-early` when the model showed no estimate. `harness/score.py` scores only `estimating` rows. |
| `pD` | The chance that the Democrat wins |
| `mid`, `lo`, `hi` | The median and 80% range of the final margin: Democratic minus Republican votes, as a share of all votes |
| `tmid`, `tlo`, `thi` | The median and 80% range of the final total vote |
| `truth`, `total` | The final margin and the final total vote |

## Checking the scores

You need Python 3.11 or later and no other packages.

```bash
python3 harness/score.py
```

```bash
python3 harness/figures.py
```

```bash
python3 harness/compare.py
```

`score.py` reads `outputs/estimates.jsonl`, prints the scores, and writes `outputs/scores.json`. `figures.py` redraws the figures in `figures/` from `outputs/scores.json`. `compare.py` scores the model and both versions of the regression nowcast on the checkpoints where both the model and the nowcast gave an estimate, prints the scores, and writes `outputs/comparison-narrow.json` and `outputs/comparison-wide.json`. For each group of races, those files also record the scores at stricter call thresholds and, under `speed`, how far into the count each forecast made its call for the races that both called correctly.

## Replaying the races

Replaying the races needs Node.js 24 or later, the main repository at the pinned commit, and county results for every race.

1. Check out the main repository next to this one:

   ```bash
   git clone https://github.com/electarchive/electionsarchive ../electionsarchive
   ```

   ```bash
   git -C ../electionsarchive checkout bb3e39cfdc52d30c2b005f1213b402c130f1a28b
   ```

2. Put the county results in `inputs/counties.json`. This file is not in the repository yet. It will come with the archive's bulk data release.
3. Download the captures from the Internet Archive into `frames/raw/`. The script checks each one against its checksum in `frames/manifest.json`. The Internet Archive limits how fast a client can download, so the script waits between captures, and downloading all of them takes a few hours.

   ```bash
   python3 harness/fetch.py
   ```

4. Rebuild the county counts over time into `frames/2020.json`, `frames/2022.json`, and `frames/holdout.json`. The script prints each held-out race it leaves out and the reason.

   ```bash
   python3 harness/build.py
   ```

5. Replay every race through the model. This writes `outputs/estimates.jsonl`.

   ```bash
   node harness/replay.ts sets=2020,2022,holdout,simulated
   ```

6. Replay every race through both versions of the regression nowcast. This writes `outputs/baseline-narrow.jsonl` and `outputs/baseline-wide.jsonl`.

   ```bash
   MODEL=harness/baseline.ts node harness/replay.ts sets=2020,2022,holdout,simulated name=baseline-narrow
   ```

   ```bash
   MODEL=harness/baseline.ts BASELINE=wide node harness/replay.ts sets=2020,2022,holdout,simulated name=baseline-wide
   ```

`replay.ts` takes these options:

- `MAIN=<path>` (an environment variable) points to the main repository, if it is not at `../electionsarchive`.
- `sets=2020,2022,holdout,simulated` picks which nights to replay. Without it, `replay.ts` replays `2020,2022,simulated` and leaves out the held-out races.
- `part=k/n` replays every nth race, starting at race k, and writes `outputs/estimates.k.jsonl`, so you can run n parts at once and join them with `cat`.
- `out=<folder>` writes the output somewhere other than `outputs/`.
- `name=<name>` names the output file `<name>.jsonl`, or `<name>.k.jsonl` with `part`, instead of `estimates`.
- `MODEL=<path>` (an environment variable) replays a different model file that exports the same `estimate` function, such as `harness/baseline.ts`.
- `BASELINE=wide` (an environment variable) switches `harness/baseline.ts` to its wide version.

To rebuild `inputs/covariates.json`, put these files in `inputs/sources/` and run `python3 harness/covariates.py`:

- `education.csv` from the USDA Economic Research Service [county-level data sets](https://www.ers.usda.gov/data-products/county-level-data-sets/)
- `2020_Gaz_counties_national.txt` and `2022_Gaz_counties_national.txt` from the Census Bureau [Gazetteer files](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html)
- `cc-est2019-alldata.csv` from the Census Bureau [county population estimates by characteristics, 2010 to 2019](https://www.census.gov/data/tables/time-series/demo/popest/2010s-counties-detail.html)

We ran the ablations in section 6 of the paper with a research copy of the model, so the harness here does not rerun them. `outputs/ablations.json` records their results.

## November 3, 2026

We are recording the count of the November 3, 2026 elections and the model's estimates at every update. Once the results are final, we will add them here with the model's scores. They will be the first test on races held after the model was built.

## License

The code, outputs, and paper are licensed under the GNU Affero General Public License, version 3. See [LICENSE](LICENSE). The captured results pages are not included; `harness/fetch.py` downloads them from the Internet Archive.
