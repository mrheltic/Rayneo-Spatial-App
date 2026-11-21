# Linux numeric baseline

Status: **preliminary** (2026-11-21). First Linux run of the portable suites, before the
distribution packages were installed (built against the installed hidapi-hidraw runtime and
temporary headers; the code under test is identical). Re-run after `scripts/linux/setup-dev.sh`
and replace this note.

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

Main suspect: the synthetic IMU noise. `HeadSim` (`src/tools/pose_scenarios.cpp`) draws from
`std::mt19937` (sequence fixed by the standard) through `std::normal_distribution<float>`, whose
algorithm is **implementation-defined**. libstdc++ and MSVC therefore feed the estimator
*different noise sequences* from the same seed. Every scenario sees a different noise
realisation, not only scenario 10. Scenario 10 is the one that sits near a tipping point (a
1.5 deg/s bias at the clamp, 10 minutes of escape/rollback decisions).

libm (`atan2`, `exp`, `sin`) is a second, smaller source: the noiseless scenario 17 still differs
(+/-0.0174 here, +/-0.025 on MSVC).

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

1. Test the hypothesis: give `HeadSim` a portable normal generator (Box-Muller on raw `mt19937`
   output, which the standard fixes) behind a test-only switch. Then run MSVC and Linux on the
   *same* noise. If scenario 10 still diverges, the cause is libm or the estimator's FP path, and
   it needs a closer look before any Linux numbers count as a contract.
2. Run scenario 10 over several seeds on both platforms. A runaway on some seeds would be an
   estimator robustness finding in its own right, not a Linux quirk.
3. Replay real data (`imu_replay --stats`, `--startup-audit`). Real data uses no
   `normal_distribution`, so this is the cleanest check that the Linux estimator behaves like the
   Windows one. The 2026-09-25 recording that AGENTS.md's replay numbers come from is held only by
   the original author (no upstream release carries it): ask upstream, or record on Linux.
