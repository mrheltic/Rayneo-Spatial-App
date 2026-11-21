# Linux numeric baseline

Status: 2026-11-21. Re-run with the distribution packages installed (`setup-dev.sh`): same
results as the first, pre-install run, value for value.

Machine: Ubuntu 26.04, x86-64, GCC 15.2.0 and Clang 21.1.8, libstdc++, glibc, RelWithDebInfo.

## Result

| Suite | GCC | Clang |
|---|---|---|
| camera_selftest | PASS | PASS |
| pose_selftest | PASS | PASS |
| mag_heading_selftest | PASS | PASS |
| pose_scenarios | **FAIL (1)**: scenario 10 | **FAIL (1)**: scenario 10 |
| orientation_calibration_selftest | PASS | PASS |
| protocol_selftest | PASS | PASS |
| layout_selftest | PASS | PASS |
| view_selftest | PASS | PASS |

The build has no warnings under `-Wall -Wextra -Wpedantic` with either compiler.

## The scenario 10 failure

`band-limit bias settles to a bounded offset, no runaway`: **90.6893 deg** against a limit of
40 deg (MSVC: 29.2 deg). AGENTS.md section 7 already records this exact value for g++ ("runs
away under g++ (90.6 deg)") and calls the scenario's escape/rollback thresholds FP-chaotic across
compilers. The limit was **not** loosened.

New evidence: GCC and Clang print **identical** `pose_scenarios` output, every value to the last
digit. Two different compilers giving the same result points away from code generation and
towards the **standard library**: both use libstdc++ and glibc here, MSVC uses its own STL and CRT.

Noise is one factor. `HeadSim` (`src/tools/pose_scenarios.cpp`) draws from `std::mt19937`
(sequence fixed by the standard) through `std::normal_distribution<float>`, whose algorithm is
**implementation-defined**, so libstdc++ and MSVC feed the estimator different noise from the same
seed. libm (`atan2`, `exp`, `sin`) is a smaller second source: the noiseless scenario 17 still
differs (+/-0.0174 here, +/-0.025 on MSVC). But swapping in a portable generator (Box-Muller on raw
`mt19937` words) only moves scenario 10 from 90.69 to 58.6 deg. It still fails.

### Scenario 10 is seed-dependent, and the simulator leaves the band it tests

Reproduce: `scripts/linux/scenario10_experiment.py` (instrumented copy in a temp dir; the repo is
not modified). 40 seeds per row, GCC, RelWithDebInfo flags:

| Variant | min | median | max | mean | fails (>= 40) | fails with final true \|bias\| > 1.5 |
|---|---:|---:|---:|---:|---:|---:|
| std noise, bias random walk on (as shipped) | 0.06 | 27.03 | 196.90 | 41.47 | 14 | 13 of 14 |
| portable noise, walk on | 0.04 | 43.90 | 185.33 | 58.84 | 21 | 20 of 21 |
| std noise, walk off | 0.01 | 0.63 | 32.18 | 6.92 | 0 | (true bias stays 1.5 +/- 0.02) |
| portable noise, walk off | 0.04 | 6.61 | 49.07 | 10.67 | 2 | (true bias stays 1.5 +/- 0.02) |

Findings:

1. **The shipped seed's result is one draw from a wide distribution.** As shipped, scenario 10 ranges
   from 0.06 to 197 deg across seeds and fails on 35% of them under libstdc++. MSVC's 29.2 deg passes
   on its own noise; it does not show the behaviour is bounded.
2. **The main cause is the scenario, not Linux and not the estimator's FP path.** The true bias starts
   at exactly the band limit (1.5 deg/s) and the simulator's per-sample random walk
   (`bias_walk_degs = 5e-4`, about 0.27 deg/s rms per axis over 10 min) carries it outside the band in
   more than half the seeds. AGENTS.md section 4 says a bias above 1.5 deg/s cannot be corrected and
   shows as creep. That is what these runs show. Default seed: final true |bias| 1.92 deg/s, drift
   accelerating over the last minutes (-0.3 0.2 1.1 3.1 3.9 6.4 15.5 31.3 60.1 90.7 deg).
   With the walk off the same seed gives 0.12 deg.
3. **A smaller residual remains.** A bias held at exactly the clamp still spreads its outcome
   (up to 49 deg with portable noise, 2 of 40 over the limit). The estimator sits on the clamp edge
   there. That is a robustness question for the estimator owner, not a port issue.

Not changed: the scenario, its limit, the estimator. Fixing scenario 10 (e.g. no walk, or a walk
reflected inside the band, plus a seed sweep instead of one seed) changes the MSVC contract too,
so it goes to upstream (issue #1) rather than being made unilaterally here.

## Comparison with the MSVC tables (AGENTS.md section 5)

| Behaviour | MSVC | Linux (GCC = Clang) | Assertion |
|---|---:|---:|---:|
| Pan-and-return +/-60 deg (1/2) | +0.082 / -0.182 | +0.098 / +0.076 | < 0.3 |
| Slow pan, 10 deg (4) | 99.9% | 98.9% | >= 80% |
| Fast pan, 120 deg (5) | 100.0% | 99.99% | >= 95% |
| Residual 0.5 deg/s bias (6) | 0.028 | 0.071 | < 0.5 |
| Breathing + bias (7) | 0.232 | 0.230 | < 0.4 |
| Band-limit bias, 10 min (10) | 29.2 | **90.69** | < 40 |
| 1.0 deg/s for 20 s (11): at stop / reverse / offset | 89.0% / 0.125 / 2.318 | 88.3% / 0.139 / 2.472 | >= 80% / < 0.25 / < 4 |
| Micro adjustments, max step (12) | 0.0216 | 0.0216 | < 0.05 |
| Bias step learned (13): estimate / drift | 0.915 / 1.153 | 0.859 / 1.126 | > 0.7 / < 3.0 |
| 1-euro tremor residual (15) | 0.040 | 0.047 | < 0.06 |
| 5-min computer use (16) | 0.038 | 0.474 | < 3.0 |
| Noiseless closure (17) | +/-0.025 | +/-0.017 | < 0.05 |
| 20 look-arounds (18) | 0.62 | -0.74 | < 1.0 |
| Reading hold, medium (19) | 0.090 | 0.090 | < 0.2004 |
| Contaminated startup (20): unconfirmed / confirmed | 46.5 / 9.7 | 46.2 / 9.5 | > 10 / >= 70% removed |
| Single-episode reseed (25): gap / after | 15.56 / 6.00 | 15.42 / 5.95 | |
| Exposure (27) | 22.37 | 22.41 | <= 25% worse |
| Slow nods (28): worst drift | 0.020 | 0.029 | within 0.1 of no rule |

Values sit in the same neighbourhood except scenario 10 (fails) and scenario 16 (12x larger but
well inside its bound). Scenario 16 is the next one to watch.

## Next steps (phase 1)

1. Agree a scenario 10 fix with upstream (see above). Until then, `pose_scenarios` on Linux is
   expected to fail scenario 10 only; any other failure is a regression.
2. Replay real data (`imu_replay --stats`, `--startup-audit`). Real data uses no
   `normal_distribution`, so this is the cleanest check that the Linux estimator behaves like the
   Windows one. The 2026-09-25 recording behind AGENTS.md's replay numbers is held only by the
   original author (requested in issue #1); otherwise record on Linux once the IMU enumerates.
