# Pre-registration: November 3, 2026

We wrote this file before the polls closed in any state on November 3, 2026, and committed it before 23:00 UTC, when the first state polls close. It fixes how we will score the live forecast on that night's count: which races, which measures, what counts as a success, and what we already knew. The commit time on GitHub is the record. We will not edit this file after that commit; anything we learn later goes in a separate file.

## The model and the code

- The model is [`packages/analytics/src/live.ts`](https://github.com/electarchive/electionsarchive/blob/a11c15db502393aa9ac054c4c5db6f3c2bb3525d/packages/analytics/src/live.ts) at commit `a11c15db502393aa9ac054c4c5db6f3c2bb3525d` of the main repository.
- That commit adds one change to the model that runs on electionsarchive.com tonight: a cap on the votes the model still expects to arrive late (section "The late-count cap" below). The cap only acts after the first day of counting, so on election night both versions give the same estimates.
- The scoring code is `harness/score.py` and `harness/compare.py` at the commit that adds this file. The groups `2026` and `2026late` and the `tiered` call rule were added in the same commit.
- If we have to fix a bug in the model while the count goes on, we will score both the version that ran on the site and the version pinned here, and report both.

## The races

- We score every statewide race in the 50 states and the District of Columbia that the live board shows on November 3, 2026, where the model gives an estimate at least once and where a Democrat and a Republican finish first and second in the final count.
- We leave out races whose feed only reports a statewide total, since the model needs counts by county or town.
- We leave out the five territories. Guam and the Northern Mariana Islands had started counting before we committed this file, and our replays never covered a territory.
- We will also report the other races on the board, such as U.S. House races, but as an extra. They are not part of the tests below.
- We will list every race we leave out and the reason.

## The counts and the final results

- The counts are every update the archive's live feeds recorded from state and county election offices, from the first update until the count is final. We are saving each update as it arrives. We will rebuild them into `frames/2026.json` and replay them through the model with `harness/replay.ts`, as set `2026`.
- The final results are the certified results in the archive. We will score the night once every state in the score has certified its results, and we will publish every result, including the ones that go against the model.

## The measures

We use the same measures as the paper, computed by `harness/score.py`: the Brier score and log loss of the win chance, the weighted interval score (WIS) of the margin, how often the 80% range of the final margin holds the final margin, the median margin's mean absolute error, the median turnout's mean absolute percentage error, how often the 80% turnout range holds the final turnout, the number of estimates that gave the eventual loser 95% or more, and the calls and wrong calls. The group `2026` holds every checkpoint of the scored races. The group `2026late` holds the checkpoints at least 1,440 minutes (one day) after a race's first update.

Every interval below is a 90% bootstrap interval that resamples races, as in the paper.

## The questions

### 1. Is the model more accurate than the regression nowcast?

We replay the count through the narrow and wide versions of the regression nowcast in section 7 of the paper and compare them with the model on the same checkpoints, using `harness/compare.py`. The model wins on a measure if the interval for the paired difference excludes zero in the model's favor. Log loss and WIS are the main measures; Brier score and the margin's mean absolute error come second. On the held-out races in section 8, the model won on log loss, WIS, and mean absolute error, and the Brier interval included zero. We expect the same tonight.

### 2. Are its ranges honest?

We report how often the 80% range held the final margin, with its interval. The ranges are honest if that interval includes 80%. On the held-out races the range held the final margin 75% of the time, so we expect it to fall a little short again.

### 3. Does the rule on our board make any wrong call?

The board marks a race ready to call when the model gives the leader at least 99.5% and estimates that at least half the vote is counted. We expect no wrong calls. We will report every call, with the share counted when it was made, and describe any wrong call race by race.

### 4. The tiered call rule

The tiered rule keeps the board's rule and adds a second way to call: at least 99.999% for the leader with at least 20% of the vote counted. It is not on our board tonight. We will report how many races it calls, how many it gets wrong, and the mean share counted when it calls. If it makes even one wrong call, we drop it. If it makes none, we will consider it for the board in later elections.

What we knew when we chose it: We picked the rule at 20:12 UTC on November 3, 2026, on the simulated nights and the real nights we tuned the model on. On those nights it made no wrong calls, and the mean share counted at a call fell from 56.1% to 38.0% on the simulated nights. We had not scored it on the held-out races, but we already knew of three held-out races (2020 Massachusetts, 2020 Montana, and 2024 California) where the model gave the leader at least 99.99% with just under half the vote counted. Scored afterward on the held-out races, the rule called 66 of 73 races, got none wrong, and called at 83.0% counted on average, against 86.7% for the board's rule.

### 5. Does the model call earlier than the regression nowcast?

For the races that both call correctly, we compare the mean share counted at the first call, under the board's rule and under the tiered rule. On the held-out races the model called later than the nowcast under both rules: at 86.4% counted against 83.8% and 84.5% under the board's rule. Depending on the version and the rule, the nowcast called first in 7 to 10 races, and the model called first in none. The nowcast's speed came at a cost: it called all 73 held-out races and got 7 of them wrong under the board's rule and 8 under the tiered rule, while the model got none wrong under either. We expect the model to call later again tonight, and we will report how much later, along with every wrong call by either forecast.

### 6. The late-count cap

In states that count late ballots for days or weeks, the model used to keep expecting the full share of late votes even after many of them had been counted, so its turnout estimate kept rising. The cap limits the votes still expected late to the state's late share of the election-night total, less the late votes already counted. We replay the count through the model with the cap (commit `a11c15db502393aa9ac054c4c5db6f3c2bb3525d`) and without it (commit `200a4d2a731cb9087abed90e30a23dde96f8a33f`), and compare the two on the `2026late` checkpoints with `harness/compare.py`, writing the second replay as `outputs/baseline-nocap.jsonl`. The cap helps if the interval for the paired difference in turnout error excludes zero in its favor. We also report the 80% turnout range's coverage and the win-chance measures, which should not get worse.

What we knew: We designed the cap after looking at turnout errors on every real night, the held-out races included, so its gains there are not an independent test. On those nights it lowered the median turnout's mean absolute percentage error from 3.80% to 3.57% on the races we tuned on, from 10.81% to 10.12% on the held-out 2022 races, and from 7.09% to 5.58% on the held-out 2024 races. It changed no call, and it left every simulated checkpoint the same. Tonight's count is its first real test.

## Publishing

Once the results are certified, we will add a section to the paper with the answers to all six questions, the scores for every group, and the list of races we left out, and we will add the replays to `outputs/`.
