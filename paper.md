# Estimating final results from partial county counts on election night

electionsarchive.com, November 3, 2026

## Summary

On election night, electionsarchive.com estimates each race's final margin, its final turnout, and each candidate's chance of winning from county counts as they come in. This paper describes the model, the backtest we ran on it, and its scores.

The model projects each county's final turnout and margin from an earlier election, the counties that have already reported, and county demographics, and it simulates the uncounted vote 500 times. Two of its parts get most of the attention here:

1. **Vote-mode swings measured within the count.** Mail, early in-person, and Election Day votes often lean different ways, and counties count them in different orders. The model compares, county by county, the margin among the votes counted later with the margin among the votes counted earlier. When those swings are larger than ordinary differences between batches, it adds a shared shock to the votes still out, in proportion to how many remain.
2. **Averaged win chances.** Instead of reporting the share of simulations each candidate wins, the model computes each candidate's chance within every simulation, by integrating out the shared Gaussian shocks in closed form, and averages those chances. This is a Rao-Blackwellized estimate: it has the same expectation as the share of simulations won, with less simulation noise.

We replayed 477 simulated nights and 12 real ones, county by county, scored the model at every checkpoint, and tuned its settings on those nights. On the simulated nights (7,623 checkpoints), the Brier score is 0.021 (90% interval 0.016 to 0.026), the log loss is 0.067 (0.052 to 0.081), and the 80% range held the final margin 87% of the time. Under the site's call rule, the model called 436 of the 477 races, at a mean of 56% of the vote counted, and called none wrong.

The real nights are the 2020 presidential count in Florida, Georgia, North Carolina, and Pennsylvania, and 8 Senate and governor races in 2022 (255 checkpoints). On them, the Brier score is 0.080 (0.045 to 0.127), the log loss is 0.250 (0.145 to 0.389), and the 80% range held the final margin 70% of the time. The model called 7 of the 12 races and called none wrong. At 2 of the 255 checkpoints, it gave the eventual loser a chance of 95% or more.

Ablations show that the vote-mode term does most of the work on real nights. Without it, real-night log loss rises from 0.250 to 0.391, and the number of checkpoints that gave the eventual loser 95% or more rises from 2 to 11.

We also compared the model with a regression nowcast of the kind the academic literature on election-night forecasting describes, replayed on the same nights (section 7). On the 12 real nights, its middle estimates are about as accurate as the model's, but its ranges are far too narrow. It gave the eventual loser 95% or more at 61 or 62 of the 255 real checkpoints, against the model's 2, and it called the 2020 presidential race in Georgia and in Pennsylvania for the candidate who lost. Its real-night log loss is 1.64 to 1.68, against the model's 0.25. On the 2022 races alone, its Brier score is slightly better than the model's.

Because we tuned the model on those nights, their scores are in-sample. To test the model on races it had never seen, we fixed a selection rule before scoring any new race and replayed every other statewide race from 2020, 2022, and 2024 that the Internet Archive captured often enough: 73 races and 979 checkpoints (section 8). On those held-out races, the model's Brier score is 0.009 (0.004 to 0.014), its log loss is 0.035 (0.016 to 0.055), and its 80% range held the final margin 75% of the time. It gave the eventual loser 95% or more at 1 checkpoint, and it called 66 of the 73 races, none wrong. It scored better than both versions of the regression nowcast on log loss, interval score, and the error of the middle estimate, and the intervals on those differences exclude zero. Its Brier score is lower too, but the intervals on those differences include zero.

The model is not faster to call. On the held-out races that both called correctly, the regression nowcast called at a mean of 84% (narrow) or 85% (wide) of the vote counted, against the model's 86%, but it called 7 of the 73 races for the candidate who lost. Under the site's call rule, none of the model's calls was wrong on any night we replayed, simulated or real.

The count of the November 3, 2026 elections is the first test on races held after the model was built. We will add it here once the results are final.

## 1. The model

The model is [`packages/analytics/src/live.ts`](https://github.com/electarchive/electionsarchive/blob/bb3e39cfdc52d30c2b005f1213b402c130f1a28b/packages/analytics/src/live.ts) in the main electionsarchive.com repository. The [methodology page](https://electionsarchive.com/live/methodology) explains it for general readers. The backtest depends on the following parts.

### 1.1 Inputs

For each race, the model reads:

- each county's cumulative count for each candidate, at every update;
- each county's result in a baseline election: the last race for the same seat, or the last presidential race when that race was one-sided or missing;
- each county's expected total vote, from the same past races;
- four county demographic shares: adults with a bachelor's degree, and white, Black, and Hispanic residents.

### 1.2 Turnout

The model treats each reporting county as finished, with a final total just above its current count, or still counting, with a final total above its count and most likely near its expected turnout. The chance that a county is finished depends on how turnout compares with expectations across the state, how closely counties follow that statewide level, what share of counties have finished, and how long the county's count has gone unchanged: 15 minutes, or twice its usual time between updates if that is longer. Counties with no votes yet are expected to cast their usual turnout, scaled by the statewide turnout level seen so far.

### 1.3 Swing

For each reporting county, the model compares the margin counted so far with the county's baseline margin. Across reporting counties, it fits a uniform swing and four effects: a stronghold effect (the swing grows or shrinks with the baseline margin), a county-size effect, a demographic effect, and a count-order effect (the margin among a county's later votes differs from the margin among its earlier ones). Each effect starts near zero and grows only as the counts support it. Each county's projected margin blends its own count with the fitted prediction, and the more of a county's vote is in, the more weight its own count gets.

### 1.4 Simulation

Each of 500 simulations draws every county's final turnout and margin, then adds up the counties. Each simulation includes three shared shocks, so that errors in different counties do not cancel out:

- a statewide shift with standard deviation 0.028 × √(1 − f_c) in each county c, where f_c is the share of the county's expected vote already counted;
- the vote-mode shock described in section 2;
- a late-count allowance in states that count many ballots after election night, sized from each state's history, with a shared lean with standard deviation 0.06.

The 80% range for the final margin runs from the 10th to the 90th percentile of the 500 simulated final margins. The chance of winning comes from section 3.

A race shows no estimate until 10% of its expected vote is counted and at least three of its counties have reported, or every county when it has fewer than three.

## 2. Vote-mode swings measured within the count

For each county that has reported more than once, the model picks the earlier snapshot that splits the county's votes most evenly between "before" and "after." Among snapshots with e < 0.9 T, it picks the one that maximizes e (T − e), where e is the count at that snapshot and T is the latest count. Let m_e be the margin among the votes counted by then, and m_l the margin among the votes counted since. With w_c = min(e, T − e), the model pools these swings across counties and shrinks them toward a prior:

```math
V^2 = \frac{\kappa \sigma_0^2 + \sum_c w_c \, (m_l - m_e)^2}{\kappa + \sum_c w_c}, \qquad \kappa = 0.02 \sum_c E_c, \quad \sigma_0 = 0.1
```

where E_c is county c's expected final vote. Some swing between batches is ordinary, and the county-level noise in each simulation already covers it. Only the part above a calm level of 0.2 counts:

```math
s = 0.9 \sqrt{\max\left(0,\; V^2 - 0.2^2\right)}
```

Because the prior σ₀ = 0.1 is below the calm level, s stays at zero until the count itself shows swings beyond it. In each simulation, the model draws z ~ N(0, 1) and moves each county's projected final margin by s · z · (1 − f_c), before clamping to the votes that remain. That is the same as moving the margin among each county's uncounted votes by s · z, so the shock grows with the votes still out and fades as counties finish.

## 3. Averaged win chances

The statewide shift, the vote-mode shock, and the late-count lean are Gaussian, and each enters the statewide lead linearly, as long as no county's projected lead hits the clamp. So, within simulation k, the model computes the lead without those three shocks (μ_k) and their combined standard deviation:

```math
\sigma_k = \frac{1}{N}\sqrt{\left(0.028 \sum_c F_c \sqrt{1 - f_c}\right)^2 + \left(s \sum_c F_c (1 - f_c)\right)^2 + \left(0.06 \sum_c L_c\right)^2}
```

where F_c is county c's projected final vote, L_c its projected late-count vote, and N the projected statewide total. Counties whose projected lead is clamped are left out of the sums. The reported chance is

```math
P(\text{A wins}) = \frac{1}{K} \sum_{k=1}^{K} \Phi\!\left(\frac{\mu_k}{\sigma_k}\right), \qquad K = 500
```

This has the same expectation as the share of simulations that candidate A wins, but less variance. With 500 simulations, the share won moves by about 0.3 percentage points between updates from simulation noise alone near a 99.5% call threshold, so a race can cross the threshold and back for no reason. The averaged chance removes most of that noise.

## 4. Backtest design

### 4.1 Simulated nights

The simulated nights start from every certified statewide race for president, Senate, and governor from 2012 to 2024 in which both major parties won at least 20% of the vote, in a state with at least 3 counties. Alaska, the District of Columbia, and Puerto Rico are left out. That leaves 477 races. A generator splits each county's final result into Election Day, early in-person, and mail votes, with shares and margin gaps drawn by year (larger gaps in 2020, smaller before). It releases those votes in county batches in one of three orders (mail first, Election Day first, or mixed), and holds back a late count sized by state. The generator is in `harness/replay.ts`. Checkpoints fall at 3%, 10%, 20%, and every 5 points from 25% to 95% of the final vote: 7,623 in all, counting only checkpoints where the model gave an estimate.

Four of these races don't replay correctly: Connecticut's 2022 races for governor and Senate, and its 2024 races for president and Senate. Their results are by the planning regions that replaced Connecticut's counties in 2022, while their baseline, the 2020 presidential race, is by county, and the replay can't match the two. In those races, the model assumes that both the old counties and the new regions cast ballots, so it projects about twice the real turnout and calls none of them. We left them in the scores in section 5. Without them, the simulated turnout error is 4.4% instead of 5.2%, the model called 436 of 473 races, and the Brier score, log loss, and 80% range coverage barely change. The live forecast uses the 2024 presidential results as the baseline for Connecticut, and those are by planning region, so it doesn't have this problem.

The simulated nights test the model against the generator's assumptions, not against real counting.

### 4.2 Real nights

We rebuilt county counts over time from The New York Times results pages, as captured by the Internet Archive's Wayback Machine: 167 captures of the 2020 presidential race in Florida, Georgia, North Carolina, and Pennsylvania, and 132 captures of 8 races in 2022 (Arizona governor, and the Senate races in Arizona, Georgia, Nevada, North Carolina, Ohio, Pennsylvania, and Wisconsin). `frames/manifest.json` lists every capture with its checksum. Baselines and final results come from the certified county results in electionsarchive.com: the 2016 presidential results for 2020, and the 2020 presidential results for 2022, with expected turnout scaled by each county's 2018 to 2016 turnout ratio. Each capture with at least 5% of the final vote counted is a checkpoint: 165 in 2020 and 90 in 2022.

The captures are irregular, sometimes hours apart, and the model sees only the counts in each capture.

### 4.3 Scoring

At every checkpoint, we score:

- **Brier score** and **log loss** of the chance given to the eventual winner. Log loss clips chances to [0.001, 0.999].
- **Interval score** of the margin forecast: the weighted interval score with the median and the 80% range (α = 0.2), in percentage points.
- **80% range coverage**: the share of checkpoints whose final margin falls inside the range.
- **Error of the middle estimate**: the mean absolute difference between the median simulated margin and the final margin, in percentage points.
- **Turnout error** and **turnout coverage**: the mean absolute percentage error of the median final total, and the share of checkpoints whose final total falls inside the 80% turnout range.
- **Confident misses**: checkpoints that gave the eventual loser 95% or more.
- **Calls** under the site's call rule: a race is called at the first checkpoint where a candidate's chance reaches 99.5% and the model estimates that at least half the vote is counted. A wrong call names the eventual loser.
- **Flips**: how often per race the favored candidate changes between checkpoints.
- **Expected calibration error**: the mean absolute gap between stated chance and observed frequency across eight bins, weighted by checkpoints.

Checkpoints within a race are strongly correlated, so we put intervals on the scores by resampling races, not checkpoints: 2,000 resamples, clustered by race, with a fixed seed. The intervals are 90% percentile intervals.

## 5. Results

### 5.1 Scores

| Measure | Simulated | Simulated, decided by under 10 points | Real, 2020 | Real, 2022 | Real, both years |
|---|---|---|---|---|---|
| Races | 477 | 153 | 4 | 8 | 12 |
| Checkpoints | 7,623 | 2,453 | 165 | 90 | 255 |
| Brier score | 0.021 (0.016–0.026) | 0.063 (0.049–0.079) | 0.062 (0.005–0.085) | 0.113 (0.030–0.201) | 0.080 (0.045–0.127) |
| Log loss | 0.067 (0.052–0.081) | 0.200 (0.161–0.240) | 0.196 (0.019–0.293) | 0.351 (0.122–0.589) | 0.250 (0.145–0.389) |
| Interval score | 1.03 (0.97–1.09) | 0.91 (0.83–0.99) | 0.63 (0.11–1.02) | 0.98 (0.55–1.49) | 0.75 (0.40–1.07) |
| 80% range coverage | 87% (85–88%) | 88% (85–90%) | 68% (44–100%) | 73% (49–94%) | 70% (52–93%) |
| Error of the middle estimate | 1.49 (1.40–1.58) | 1.33 (1.20–1.48) | 1.04 (0.17–1.72) | 1.41 (0.82–2.12) | 1.17 (0.58–1.68) |
| Turnout error | 5.2% | 3.0% | 1.2% | 8.6% | 3.8% |
| Turnout coverage | 71% | 74% | 32% | 23% | 29% |
| Confident misses | 1 | 1 | 0 | 2 | 2 |
| Races called | 436 | 116 | 3 | 4 | 7 |
| Wrong calls | 0 | 0 | 0 | 0 | 0 |
| Mean share counted at call | 56% | 64% | 98% | 98% | 98% |
| Flips per race | 0.19 | 0.58 | 0.75 | 0.50 | 0.58 |
| Expected calibration error | 0.012 | 0.035 | 0.122 | 0.163 | 0.136 |

Lower is better for every measure except coverage, where closer to 80% is better, and races called, where more is better. With a looser 99% call threshold, the model calls 440 simulated races and the same 7 real races, still with no wrong calls.

Real nights are harder than simulated ones for the chance of winning: the Brier score and log loss are about four times as high, and the 80% range held the final margin less often. The real races were among the closest of their years, and the counts in 2020 were unusual. The interval score is lower on real nights because most real checkpoints come late in the count, when ranges are narrow: 189 of the 255 come after 95% of the vote is counted.

On real nights, the model calls races late, at about 98% of the vote counted. Part of that is the captures: they are often hours apart late in the count, so the first capture past the call rule can come well after the moment the model would have crossed it.

The two confident misses are both from 2022. In the North Carolina Senate race, with 48% of the vote counted, the model gave the Democrat a 98% chance, and the Republican won by 3.2 points. In the Nevada Senate race, with 82% counted, the model gave the Democrat a 5% chance, and the Democrat won by 0.8 points, on mail ballots counted over the following days.

### 5.2 Calibration

![Calibration on real nights](figures/reliability-real.svg)

![Calibration on simulated nights](figures/reliability-simulated.svg)

On simulated nights, the model sits close to the diagonal. On real nights, it sits above it: Democrats won more often than the model said, because the votes counted late leaned Democratic in most of these races. With 12 races, each bin holds a few races seen many times, so the real-night curve is noisy.

### 5.3 By stage of the count

![Log loss by stage of the count](figures/stages.svg)

On real nights, about four-fifths of the total log loss comes before 95% of the vote is counted, including the stretch of the 2020 count in Georgia and Pennsylvania when Election Day votes had been counted and mail votes had not. Only 2 real checkpoints fall before 50% of the vote counted, so the real-night score for that stage rests on very little.

### 5.4 Pennsylvania, 2020

The [methodology page](https://electionsarchive.com/live/methodology#replay) replays the 2020 presidential count in Pennsylvania through the model. The Internet Archive saved no copies of the results page between 3% and 66% of the vote counted. With two-thirds of the vote counted, Trump led by 15 points, and the model gave Biden an 11% chance, with an 80% range for Biden's final margin from −30.5 to +0.3 points. From 77% counted, the range held Biden's final margin of 1.2 points, and by 84% the model leaned toward Biden. From 96% counted, its middle estimate had Biden winning by 2 to 3 points, and its range missed the final margin: the last ballots still favored Biden, but by less than the mail ballots counted before them.

## 6. Ablations

Each variant changes one part of the model. We ran the variants with a research copy of the model that matches `live.ts` at its shipped settings, on all 255 real checkpoints and on a fixed half of the simulated races (240 races and 3,819 checkpoints), with the same simulated counting orders and random draws for every variant. The simulated numbers therefore differ slightly from section 5. `outputs/ablations.json` holds the results.

| Variant | Real log loss | Real Brier | Real interval score | Real coverage | Real confident misses | Simulated log loss | Simulated interval score | Simulated coverage |
|---|---|---|---|---|---|---|---|---|
| **The model as it runs** | **0.250** | **0.0801** | **0.752** | **70%** | **2** | **0.0601** | **1.071** | **87%** |
| Without the vote-mode term | 0.391 | 0.0939 | 0.878 | 51% | 11 | 0.0569 | 1.030 | 85% |
| Chance from the share of simulations won | 0.257 | 0.0821 | 0.752 | 70% | 1 | 0.0601 | 1.071 | 87% |
| Vote-mode shock fixed at s = 0.1 | 0.313 | 0.0905 | 0.825 | 57% | 7 | 0.0818 | 1.368 | 96% |
| No calm level | 0.242 | 0.0793 | 0.753 | 74% | 0 | 0.0798 | 1.383 | 96% |
| Scale 0.6 instead of 0.9 | 0.259 | 0.0828 | 0.762 | 65% | 3 | 0.0587 | 1.049 | 87% |
| Scale 1.2 instead of 0.9 | 0.251 | 0.0798 | 0.760 | 78% | 1 | 0.0615 | 1.095 | 87% |

What the ablations show:

- **The vote-mode term does most of the work on real nights.** Without it, real-night log loss rises from 0.250 to 0.391, coverage falls from 70% to 51%, and confident misses rise from 2 to 11. On simulated nights, the term costs a little (log loss 0.0601 against 0.0569), because some simulated swings widen ranges that turn out not to need it.
- **Averaging chances mostly makes the output steadier.** It barely moves the scores, and it lowers flips on simulated nights from 0.200 to 0.188 per race.
- **The vote-mode term must be measured, not fixed.** A fixed shock of the same size helps real nights less and costs simulated nights much more, because it widens every race, including the many where the count shows no swing.
- **The calm level is the main tradeoff.** Without it, real nights improve a little more, but simulated ranges become far too wide: they hold the final margin 96% of the time instead of about 80%, and the interval score worsens by about 30%. We kept the calm level at 0.2.
- The scale has little effect. Results change little between 0.6 and 1.2.

We also tried, and dropped, Student-t shared shocks with 4 degrees of freedom, a stretch of the 80% range, smoothing the chance across checkpoints, and a fixed floor on the vote-mode shock. None improved on the model in replays.

## 7. Comparison with a regression nowcast

The usual approach in the academic literature on election-night forecasting is regression: fit the swing in the areas that have reported against their results in an earlier election, and use the fit to project the areas still out. Brown and Payne (1975) describe the forecast they built this way for the BBC's coverage of the 1974 British general elections. We wrote a version of this approach for county counts, `harness/baseline.ts`, and replayed it through the same harness on the same nights.

### 7.1 The regression nowcast

At each checkpoint, the regression nowcast fits a line by weighted least squares through the counties that have reported any votes. The outcome is each county's counted margin, the predictor is its margin in the earlier election, and the weights are the counted votes. When the reporting counties' earlier margins are too alike to fit a slope, it applies the average swing instead (a slope of 1). Counties with no votes yet get the fitted margin. In counties that have partly reported, the votes still out get the county's counted margin.

The forecast of the final margin is normally distributed. Its variance adds three parts: the scatter of counties around the line, for counties with no votes yet; the uncertainty in the fitted line itself; and a term for the votes still out in partly reported counties. We ran two versions that differ only in that last term:

- **Narrow:** the votes still out are treated as a random sample of the county's voters, so the term is binomial sampling variance.
- **Wide:** the votes still out get the same scatter as a county with no votes yet.

The two versions give the same middle estimate and the same turnout forecast.

The chance of winning is the normal probability that the final margin is above zero. Neither version shows an estimate until 3 counties have reported. The turnout forecast is the expected total, with no range, so we don't compare turnout coverage.

Brown and Payne used a modified ridge regression and split constituencies into types. Ours is plain weighted least squares on counties.

### 7.2 Results

We score both versions and the model on the checkpoints where both the model and the regression nowcast gave an estimate: 7,559 checkpoints in 473 simulated races, and all 255 real checkpoints. The regression nowcast gives no estimate in the four Connecticut races described in section 4.1, so the model's simulated scores here differ from section 5. `harness/compare.py` computes the scores and puts 90% intervals on the paired differences by resampling races, as in section 4.3. It writes `outputs/comparison-narrow.json` and `outputs/comparison-wide.json`.

| Measure | Simulated: model | Simulated: regression, narrow | Simulated: regression, wide | Real: model | Real: regression, narrow | Real: regression, wide |
|---|---|---|---|---|---|---|
| Brier score | 0.021 | 0.072 | 0.065 | 0.080 | 0.243 | 0.242 |
| Log loss | 0.067 | 0.470 | 0.343 | 0.250 | 1.680 | 1.637 |
| Interval score | 1.02 | 3.26 | 2.81 | 0.75 | 1.21 | 1.10 |
| 80% range coverage | 87% | 10% | 31% | 70% | 0.4% | 6% |
| Error of the middle estimate | 1.47 | 3.50 | 3.50 | 1.17 | 1.22 | 1.22 |
| Turnout error | 4.4% | 8.0% | 8.0% | 3.8% | 5.9% | 5.9% |
| Confident misses | 1 | 511 | 353 | 2 | 62 | 61 |
| Races called | 436 | 473 | 463 | 7 | 12 | 12 |
| Wrong calls | 0 | 43 | 22 | 0 | 2 | 3 |
| Mean share counted at call | 56% | 51% | 53% | 98% | 81% | 87% |
| Expected calibration error | 0.012 | 0.070 | 0.059 | 0.136 | 0.243 | 0.246 |

The differences below are the regression nowcast's score minus the model's, with 90% intervals. A positive difference means the model scored better.

| Difference | Simulated, narrow | Simulated, wide | Real, narrow | Real, wide |
|---|---|---|---|---|
| Brier score | +0.051 (+0.037 to +0.065) | +0.044 (+0.031 to +0.057) | +0.163 (−0.020 to +0.268) | +0.162 (−0.021 to +0.268) |
| Log loss | +0.40 (+0.30 to +0.51) | +0.28 (+0.20 to +0.36) | +1.43 (+0.13 to +2.21) | +1.39 (+0.06 to +2.17) |
| Interval score | +2.24 (+2.05 to +2.44) | +1.79 (+1.61 to +1.97) | +0.46 (+0.14 to +0.66) | +0.34 (−0.02 to +0.56) |
| Error of the middle estimate | +2.02 (+1.83 to +2.23) | +2.02 (+1.83 to +2.23) | +0.04 (−0.19 to +0.23) | +0.04 (−0.19 to +0.23) |

On the simulated nights, the model scores better than both versions on every measure, and no interval on a difference includes zero.

On the real nights, the middle estimates are about equally accurate: 1.17 points of error for the model and 1.22 for the regression nowcast, and the interval on the difference includes zero. The two differ in how much uncertainty they report. The regression nowcast's 80% range held the final margin at 0.4% (narrow) and 6% (wide) of real checkpoints, and it gave the eventual loser 95% or more at 62 and 61 of the 255. Its real-night log loss is more than six times the model's, and the intervals on both log loss differences exclude zero. The intervals on the Brier score differences include zero, but only just.

Under the site's call rule, both versions called all 12 real races, and both called the 2020 presidential race in Pennsylvania and in Georgia for Trump: Pennsylvania at 66% of the vote counted and Georgia at 81%, each time giving Biden a chance under 0.1%. Biden won both. The wide version also called the 2022 Nevada Senate race for the Republican at 82% counted, and the Democrat won it. The model called 7 of the 12 real races, later in the count, and none wrong.

The regression nowcast did better on the 2022 races. Its Brier score there is 0.089 (narrow) and 0.086 (wide), against the model's 0.113, though the intervals on those differences include zero. The narrow version called all 8 races correctly at a mean of 81% counted, while the model called 4, at 98%. In 2022, the votes counted late leaned one way less sharply than in 2020, so confident calls were right more often. On nights like that, the model gives up some speed to avoid errors like those of 2020.

The regression nowcast fails in 2020 for the reason section 2 describes. It assumes that the votes still out in a county look like the votes already counted there, and that counties' departures from the fitted line are independent. When counties count Election Day votes first and mail votes later, both assumptions fail at once, in the same direction, everywhere. The model's vote-mode term measures that shared shift from the count itself.

### 7.3 Speed of calls

An early call is worth something only if it is right. Among the races that both the model and the regression nowcast called correctly under the site's call rule, the regression nowcast usually called first. On the simulated nights, it made those calls at a mean of 51% of the vote counted (narrow) or 53% (wide), against the model's 55%, and it called 166 (narrow) or 162 (wide) of those races before the model did, while the model called 74 or 87 first. On the real nights, the two called the same 6 races correctly, and the regression nowcast called 2 of them (narrow) or 1 (wide) earlier.

That speed comes with wrong calls, and raising the call threshold doesn't remove them. The tables below show, for each threshold, how many races each forecast called, how many of those calls were wrong, and the mean share of the vote counted at the call.

Simulated nights, 473 races:

| Call threshold | Model | Regression, narrow | Regression, wide |
|---|---|---|---|
| 90% | 456 called, 1 wrong, at 55% | 473 called, 43 wrong, at 51% | 471 called, 33 wrong, at 52% |
| 95% | 448 called, 0 wrong, at 55% | 473 called, 43 wrong, at 51% | 468 called, 30 wrong, at 52% |
| 99% | 440 called, 0 wrong, at 56% | 473 called, 43 wrong, at 51% | 464 called, 24 wrong, at 53% |
| 99.5% (the site's rule) | 436 called, 0 wrong, at 56% | 473 called, 43 wrong, at 51% | 463 called, 22 wrong, at 53% |
| 99.9% | 429 called, 0 wrong, at 57% | 473 called, 41 wrong, at 51% | 462 called, 21 wrong, at 54% |
| 99.99% | 420 called, 0 wrong, at 58% | 473 called, 41 wrong, at 51% | 460 called, 17 wrong, at 55% |
| 99.999% | 408 called, 0 wrong, at 58% | 473 called, 38 wrong, at 52% | 458 called, 16 wrong, at 55% |

Real nights, 12 races:

| Call threshold | Model | Regression, narrow | Regression, wide |
|---|---|---|---|
| 90% | 10 called, 2 wrong, at 91% | 12 called, 2 wrong, at 81% | 12 called, 2 wrong, at 81% |
| 95% | 9 called, 2 wrong, at 90% | 12 called, 2 wrong, at 81% | 12 called, 3 wrong, at 82% |
| 99% | 7 called, 0 wrong, at 98% | 12 called, 2 wrong, at 81% | 12 called, 3 wrong, at 87% |
| 99.5% (the site's rule) | 7 called, 0 wrong, at 98% | 12 called, 2 wrong, at 81% | 12 called, 3 wrong, at 87% |
| 99.9% | 7 called, 0 wrong, at 98% | 12 called, 2 wrong, at 81% | 12 called, 2 wrong, at 88% |
| 99.99% | 7 called, 0 wrong, at 98% | 12 called, 2 wrong, at 83% | 10 called, 2 wrong, at 86% |
| 99.999% | 7 called, 0 wrong, at 98% | 12 called, 2 wrong, at 83% | 10 called, 2 wrong, at 86% |

No threshold brings the regression nowcast's wrong calls to zero, because it gave those calls near-certain chances. Even at 99.99999%, it makes 37 (narrow) or 16 (wide) wrong calls on the simulated nights and 2 on the real nights. So the two forecasts can't be compared at equal accuracy. On the simulated nights, a model threshold of 95% calls races about as early as the wide regression nowcast does at 99.999%, with no wrong calls against its 16. On the real nights, the model is slower: it makes its 7 calls with 98% of the vote counted, and lowering its threshold to 95% brings in 2 wrong calls: the 2022 Senate races in North Carolina, for the Democrat at 48% of the vote counted, and in Nevada, for the Republican at 82%.

## 8. Held-out real nights

Sections 5 to 7 score the model on the nights we tuned it on. To see how it does on races it has never seen, we replayed every other statewide race whose New York Times results page the Internet Archive captured often enough. We fixed the rule for choosing those races in commit [`14effbc`](https://github.com/electarchive/live-forecast/commit/14effbc2b5b68823408f5fbaae3bda04c1b587be), before we replayed any of them. That commit also fixed the main comparison: the model against both versions of the regression nowcast on every held-out checkpoint, with the measures and race-clustered intervals of section 7.

### 8.1 The races

We started from every capture the Internet Archive made, from election day through 14 days after, of the New York Times statewide results pages for president and Senate in 2020, Senate and governor in 2022, and president, Senate, and governor in 2024. We left out the 12 tuning races, Alaska, and the District of Columbia, and kept a race if:

- electionsarchive.com has its certified county results and the county results of its baseline election;
- both major parties won at least 20% of the vote, the two together won at least 75%, and the state has at least 3 counties;
- the Internet Archive saved at least 3 different versions of the page.

That gave 87 races and 1,110 captures, which `frames/manifest.json` lists under `holdout` with their checksums. `harness/build.py` then left out any race that failed one of three checks:

- every reporting unit on the page must be a county in the baseline results;
- no capture may count more than 102% of the certified total;
- at least 3 captures must have 5% or more of the vote counted.

Fourteen races failed. The pages for the 2020 presidential races in Colorado, Missouri, and West Virginia and for the 2022 Senate race in Missouri counted more than 102% of the certified total at some point. The other 10 had fewer than 3 usable captures: the 2022 races for governor and Senate in Connecticut, for governor in Massachusetts, and for Senate in Iowa, Louisiana, New Hampshire, and South Dakota, and the 2024 presidential races in Arizona, Nevada, and Wisconsin. The 2022 pages for Connecticut, Massachusetts, and New Hampshire report by town, so the replay finds no county counts in them.

That leaves 73 races and 979 checkpoints:

- 2020: 52 races (42 presidential, 8 Senate, and the Senate special elections in Arizona and Georgia), with 881 checkpoints;
- 2022: 10 races (8 Senate and 2 governor), with 56 checkpoints;
- 2024: 11 races (6 presidential and 5 Senate), with 42 checkpoints.

27 of the 73 races were decided by under 10 points. Baselines follow the tuning nights: the 2016 presidential results for 2020 races, and the 2020 presidential results for 2022 and 2024 races, with expected turnout in 2022 scaled as in section 4.2. As before, each capture with at least 5% of the final vote counted is a checkpoint. Most checkpoints come late in the count: 69% come after 95% of the vote is counted, and only 13 come before 50%.

### 8.2 Scores

| Measure | All 73: model | All 73: regression, narrow | All 73: regression, wide | Under 10 points: model | Under 10 points: regression, narrow | Under 10 points: regression, wide |
|---|---|---|---|---|---|---|
| Races | 73 | 73 | 73 | 27 | 27 | 27 |
| Checkpoints | 979 | 979 | 979 | 379 | 379 | 379 |
| Brier score | 0.009 | 0.021 | 0.020 | 0.023 | 0.050 | 0.047 |
| Log loss | 0.035 | 0.149 | 0.117 | 0.087 | 0.348 | 0.277 |
| Interval score | 0.58 | 1.03 | 0.97 | 0.42 | 0.70 | 0.68 |
| 80% range coverage | 75% | 1.8% | 4% | 77% | 0.5% | 1.6% |
| Error of the middle estimate | 0.85 | 1.04 | 1.04 | 0.65 | 0.72 | 0.72 |
| Turnout error | 4.4% | 4.2% | 4.2% | 3.5% | 3.5% | 3.5% |
| Turnout coverage | 25% | | | 25% | | |
| Confident misses | 1 | 21 | 16 | 1 | 19 | 15 |
| Races called | 66 | 73 | 73 | 20 | 27 | 27 |
| Wrong calls | 0 | 7 | 7 | 0 | 6 | 6 |
| Mean share counted at call | 87% | 83% | 84% | 89% | 83% | 84% |
| Expected calibration error | 0.019 | 0.022 | 0.021 | 0.049 | 0.050 | 0.048 |

The model's 90% intervals on all 73 races are 0.004 to 0.014 for the Brier score, 0.016 to 0.055 for log loss, and 68% to 82% for 80% range coverage. The differences below are the regression nowcast's score minus the model's, with 90% intervals. A positive difference means the model scored better.

| Difference | All 73, narrow | All 73, wide | Under 10 points, narrow | Under 10 points, wide |
|---|---|---|---|---|
| Brier score | +0.013 (−0.001 to +0.032) | +0.011 (−0.001 to +0.028) | +0.027 (−0.006 to +0.078) | +0.024 (−0.006 to +0.068) |
| Log loss | +0.11 (+0.01 to +0.26) | +0.08 (+0.01 to +0.18) | +0.26 (+0.02 to +0.64) | +0.19 (+0.01 to +0.45) |
| Interval score | +0.44 (+0.31 to +0.58) | +0.39 (+0.27 to +0.52) | +0.28 (+0.16 to +0.39) | +0.26 (+0.14 to +0.37) |
| Error of the middle estimate | +0.20 (+0.08 to +0.32) | +0.20 (+0.08 to +0.32) | +0.07 (−0.05 to +0.18) | +0.07 (−0.05 to +0.18) |
| Turnout error | −0.3 (−1.2 to +0.7) | −0.3 (−1.2 to +0.7) | +0.1 (−1.0 to +1.4) | +0.1 (−1.0 to +1.4) |

The main comparison favors the model. Against both versions of the regression nowcast, the intervals on the differences in log loss, interval score, and error of the middle estimate exclude zero. The model's Brier score is lower too, but the intervals on those differences include zero, just barely. On the 27 races decided by under 10 points, the log loss and interval score differences still exclude zero, and the middle estimates are about equally accurate.

As on the tuning nights, the two forecasts differ most in how much uncertainty they report. The model's 80% range held the final margin at 75% of held-out checkpoints, somewhat less often than it should. The regression nowcast's range held it at 1.8% (narrow) and 4% (wide), and it gave the eventual loser 95% or more at 21 (narrow) and 16 (wide) checkpoints, against the model's 1.

By year:

| Year | Forecast | Brier score | Log loss | Interval score | 80% range coverage | Turnout error | Confident misses | Races called | Wrong calls |
|---|---|---|---|---|---|---|---|---|---|
| 2020 (52 races, 881 checkpoints) | Model | 0.007 | 0.028 | 0.58 | 75% | 3.9% | 1 | 50 | 0 |
| | Regression, narrow | 0.009 | 0.064 | 1.00 | 2% | 3.3% | 8 | 52 | 5 |
| | Regression, wide | 0.009 | 0.054 | 0.96 | 3.5% | 3.3% | 7 | 52 | 5 |
| 2022 (10 races, 56 checkpoints) | Model | under 0.0001 | 0.001 | 0.68 | 80% | 10.8% | 0 | 10 | 0 |
| | Regression, narrow | under 0.0001 | 0.001 | 1.51 | 0% | 18.2% | 0 | 10 | 0 |
| | Regression, wide | under 0.0001 | 0.001 | 1.30 | 7% | 18.2% | 0 | 10 | 0 |
| 2024 (11 races, 42 checkpoints) | Model | 0.066 | 0.211 | 0.66 | 74% | 7.1% | 0 | 6 | 0 |
| | Regression, narrow | 0.310 | 2.139 | 0.98 | 0% | 2.6% | 13 | 11 | 2 |
| | Regression, wide | 0.280 | 1.580 | 0.85 | 10% | 2.6% | 9 | 11 | 2 |

Most held-out races are from 2020. There, the model's advantage is in its ranges and middle estimates: the intervals on the interval score and middle-estimate differences exclude zero, while those on the Brier score and log loss differences include it. The 10 held-out races from 2022 were all lopsided, and both forecasts gave the winner near-certain chances throughout, but the model's ranges and middle estimates were closer to the final margins. In 2024, the regression nowcast gave the eventual loser 95% or more at 13 (narrow) or 9 (wide) of the 42 checkpoints, and the model at none. The intervals on the 2024 log loss differences exclude zero.

The turnout results are mixed. Across all held-out races, the two turnout errors are close, 4.4% for the model and 4.2% for the regression nowcast, and the interval on the difference includes zero. By year, the model was better in 2022 (10.8% against 18.2%) and worse in 2024 (7.1% against 2.6%), and the intervals on both of those differences exclude zero. The model's 80% turnout range held the final total at only 25% of held-out checkpoints.

### 8.3 Calls and speed

Under the site's call rule, the model called 66 of the 73 held-out races, at a mean of 87% of the vote counted, and called none wrong. The 7 races it didn't call were all decided by under 2.5 points: the 2020 presidential race in Arizona, the 2020 Senate special election in Georgia, the 2024 presidential race in Georgia, and the 2024 Senate races in Arizona, Michigan, Pennsylvania, and Wisconsin.

Both versions of the regression nowcast called all 73 races, and 7 of those calls were wrong:

- the 2020 presidential race in Michigan, for Trump at 60% of the vote counted (Biden won by 2.8 points);
- the 2020 Senate race in Michigan, for the Republican at 92% (narrow) or 96% (wide) of the vote counted (the Democrat won by 1.7 points);
- the 2020 presidential race in Ohio, for Biden at 67% (Trump won by 8.0 points);
- the 2020 presidential race in Virginia, for Trump at 61% (Biden won by 10.1 points);
- the 2020 presidential race in Wisconsin, for Trump at 78% (Biden won by 0.6 points);
- the 2024 Senate race in Michigan, for the Republican at 65% (the Democrat won by 0.3 points);
- the 2024 Senate race in Pennsylvania, for the Democrat at 98% (narrow) or 99% (wide) of the vote counted (the Republican won by 0.2 points).

Among the 61 races that both the model and the regression nowcast called correctly, the regression nowcast called at a mean of 84% (narrow) or 85% (wide) of the vote counted, against the model's 86%. It called 8 (narrow) or 7 (wide) of those races at an earlier capture than the model. The model called none of them earlier, and the two called the rest at the same capture. A forecast can call a race only at a capture, and late in the count captures are often hours apart, so these shares show which capture each forecast called at, not the moment it would have called.

Held-out nights, 73 races:

| Call threshold | Model | Regression, narrow | Regression, wide |
|---|---|---|---|
| 90% | 71 called, 1 wrong, at 86% | 73 called, 7 wrong, at 83% | 73 called, 7 wrong, at 83% |
| 95% | 71 called, 1 wrong, at 86% | 73 called, 7 wrong, at 83% | 73 called, 7 wrong, at 83% |
| 99% | 67 called, 0 wrong, at 87% | 73 called, 7 wrong, at 83% | 73 called, 7 wrong, at 83% |
| 99.5% (the site's rule) | 66 called, 0 wrong, at 87% | 73 called, 7 wrong, at 83% | 73 called, 7 wrong, at 84% |
| 99.9% | 66 called, 0 wrong, at 87% | 73 called, 7 wrong, at 83% | 73 called, 6 wrong, at 84% |
| 99.99% | 64 called, 0 wrong, at 87% | 73 called, 7 wrong, at 83% | 73 called, 6 wrong, at 84% |
| 99.999% | 63 called, 0 wrong, at 88% | 73 called, 7 wrong, at 83% | 72 called, 6 wrong, at 84% |

As on the simulated and tuning nights, no threshold brings the regression nowcast's wrong calls to zero: at every threshold from 90% to 99.999%, about 1 in 10 of its calls is wrong. The model makes no wrong calls from 99% up. Its one wrong call at 90% and 95% is the 2020 presidential race in Michigan, for Trump at 60% of the vote counted (90%) or 65% (95%).

That race also holds the model's only held-out confident miss. With 65% of the vote counted, Trump led, and the model gave him a 96% chance, with an 80% range for Biden's final margin from −6.0 to −1.1 points. The Internet Archive saved no capture between 65% and 88% counted, and by 88% the model gave Biden a 76% chance. Biden won by 2.8 points once the absentee ballots were counted. Because 96% is below the call threshold, the model didn't call the race.

On real nights, then, the model is not faster to call. The regression nowcast calls a few points earlier in the count, and about 1 in 10 of its calls is wrong.

### 8.4 Compared with the tuning nights

The model scored no worse on the held-out races than on the 12 tuning races. On the 27 held-out races decided by under 10 points, its Brier score is 0.023 (0.012 to 0.034), against 0.080 on the tuning races, and its 80% range held the final margin 77% of the time, against 70%. That doesn't mean the model does better on new races: the tuning races were among the closest of their years, so they were probably harder. But the results show no sign that the settings fit the 12 tuning races at the expense of other races.

The held-out test is not fully independent of the tuning. 52 of the 73 held-out races are from 2020, the year whose count drove the vote-mode settings. They are different races, but they share 2020's pattern of mail votes counted late.

## 9. Limitations

- **Most scores are in-sample.** We chose the vote-mode settings (the scale, the calm level, the prior, and its weight) by searching over the real and simulated nights in sections 5 to 7. The regression nowcast has no settings to tune, so those comparisons favor the model to whatever extent the tuning helped it. The held-out races in section 8 are new to the model, but most of them are from 2020, the year that drove the tuning. The November 3, 2026 count is the first test on races held after the model was built.
- **Few real races outside 2020.** Twelve tuning races and 73 held-out races give wide intervals, and most of the real-night signal comes from 2020, when the gap between mail and Election Day votes was unusually wide. The 2022 and 2024 held-out races are few, with 56 and 42 checkpoints.
- **Irregular captures.** The Internet Archive captured the results pages at irregular times, so the replays miss some updates and see others late. Most real checkpoints come after 95% of the vote is counted, so the real-night scores say little about the early count.
- **The simulated nights come from our own generator.** They test the model against assumptions we wrote, and a model that matches those assumptions scores well on them.
- **Ranges.** The model's 80% range for the margin held the final margin 75% of the time on held-out races and 70% on tuning races, so its ranges are somewhat too narrow on real nights.
- **Turnout.** The 80% range for turnout holds the final total far too rarely on real nights: 32% in 2020 and 23% in 2022 on the tuning races, and 25% on the held-out races. On the 2024 held-out races, the model's turnout error (7.1%) was worse than the regression nowcast's (2.6%). Turnout is the model's weakest part.
- **Late counts.** In states that count many ballots after election night, the late-count allowance relies on each state's history.
- **Vote types.** Most county feeds report only totals, so the model infers how late votes lean from the way counts move, not from batches labeled as mail or Election Day votes.
- **One comparison model.** The regression nowcast in sections 7 and 8 is our own version of one approach from the academic literature, adapted to US counties. Published systems add refinements, such as the ridge regression in Brown and Payne (1975), that we did not reproduce.
- **How readers understand the forecast.** These scores measure accuracy and calibration. We haven't tested how well readers understand the forecast's chances and ranges.

## 10. The November 3, 2026 count

We are recording the count of the November 3, 2026 elections as it comes in, along with the model's estimates at every update. Once the results are final, we will add those snapshots, the model's calls, and its scores here and on the [methodology page](https://electionsarchive.com/live/methodology).

## Reproducing these results

See the [README](README.md). The scores in sections 5 and 8 come from `outputs/estimates.jsonl` through `harness/score.py`, and the figures through `harness/figures.py`. The comparisons in sections 7 and 8 come from `outputs/baseline-narrow.jsonl` and `outputs/baseline-wide.jsonl` through `harness/compare.py`. The held-out races are listed under `holdout` in `frames/manifest.json`.

## References

Brown, Philip J., and Clive D. Payne. 1975. "Election Night Forecasting." *Journal of the Royal Statistical Society, Series A* 138 (4): 463–483. https://doi.org/10.2307/2345211
