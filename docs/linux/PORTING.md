# Linux port

Goal: the same spatial workspace on Linux, first for one real setup (Ubuntu 26.04, Budgie on
**labwc**, a wlroots Wayland compositor) and then for the wider Linux desktop. The Windows build
stays first-class: every Windows target is unchanged behind `if(WIN32)`.

Working rule: existing files under `src/` stay where they are (upstream merges stay cheap). Linux
code goes in new folders (`src/platform/linux/`, `src/app_linux/`); shared files only gain
`#ifdef _WIN32` / `#else` branches that leave the Windows path byte-identical.

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Fork, remotes, dev environment script, udev rule, these docs | done (fork on GitHub: see below) |
| 1 | Portable core builds and tests on Linux (gcc + clang), numeric baseline | done: warning-free with both compilers, 7/8 suites pass; scenario 10 fails because the simulated bias leaves the band it tests (`BASELINE.md`, upstream issue #1); real-data replay pending |
| 2 | Glasses on Linux (hidraw IMU, glasses output) + engine with test screens (Wayland, EGL/GLES 3) | not started |
| 3 | Virtual monitors (evdi) + capture | not started |
| 4 | Qt 6 controller over the existing app model | not started |
| 5 | Packaging (.deb, AUR), other compositors (Mutter, KWin) | not started |

## Set up a development machine

```
sudo scripts/linux/setup-dev.sh          # packages + udev rule (phases 1-2)
cmake --preset linux-gcc                 # or linux-clang
cmake --build --preset linux-gcc
ctest --preset linux-gcc
```

`setup-dev.sh --evdi` adds the virtual-display module (phase 3), `--qt` the controller toolkit
(phase 4). The first configure downloads DirectXMath (pinned commit, headers only); the SAL
annotations it expects come from `third_party/sal/sal.h`.

Remotes: `origin` is the fork (`mrheltic/Rayneo-Spatial-App`), `upstream` the original
(`AkshayReddyGujjula/Rayneo-Spatial-App`). Work happens on `linux-port`; pull estimator fixes with
`git fetch upstream && git merge upstream/main`.

## What builds on Linux today

`rayneo_core` (protocol, hidapi device, fusion, estimator, smoother, magnetometer, calibration),
`rayneo_layout`, the tools `gt_imu_probe`, `imu_replay`, `orientation_calibrate`, and the suites
`protocol_selftest`, `pose_selftest`, `pose_scenarios`, `camera_selftest`, `layout_selftest`,
`mag_heading_selftest`, `orientation_calibration_selftest`, `view_selftest`.

Not yet: `rayneo_app_model` / `app_selftest` (`app_config.cpp`, `session_logs.cpp` use Win32;
phase 4), and everything that is Windows by nature (VDD, Desktop Duplication, D3D11, Win32 UI).

## Numeric baseline (read before trusting a Linux test result)

AGENTS.md section 5 is measured on MSVC, and it warns that scenario 10's escape/rollback thresholds
are FP-chaotic across compilers (29.2 deg on MSVC, 90.6 deg under g++). The Linux suites are
therefore **not yet a contract**. Procedure, recorded in `docs/linux/BASELINE.md`:

1. Run every suite under gcc and clang; keep the full output.
2. Compare each printed value with the MSVC tables.
3. A failing assertion is investigated (libm differences, `-ffp-contract=off`), never loosened.
4. Replay a real recording with `imu_replay --stats` / `--startup-audit`. The upstream reference
   recording (`dist/reference-logs-2026-09-25.zip`) is not in the repository or in any upstream
   release; it exists only on the original author's machine. Either ask upstream for it (then the
   replay can be compared with the numbers in AGENTS.md), or record our own on Linux
   (`imu_raw.csv`) and use it as the Linux reference.

## Windows -> Linux map

| Windows piece | Linux plan | Invariant to carry over |
|---|---|---|
| hidapi (Windows backend) | hidapi-hidraw + `packaging/linux/udev/70-rayneo-gt.rules` | bug 8: never compare a write result to `length`; use `send_command_verified` |
| D3D11 flip-model swapchain on the glasses monitor | Wayland `xdg-shell` fullscreen on the glasses' `wl_output`, EGL + GLES 3 | 1: reuse `camera_view_matrix` and its `(-1,-1,-1)` signs unchanged; 8: never render onto a captured display |
| Waitable swapchain, late pose sample | `wl_surface` frame callback, pose sampled after the wait | bug 25 |
| Parsec VDD + CCD display takeover | evdi virtual connectors; arrangement through `wlr-output-management` | bug 35/37 planner (`plan_workspace_desktops`, `desktops_tile_seamlessly`) to be extracted from `src/vdd/display_config.cpp` into a Win32-free file |
| DXGI Desktop Duplication | libevdi framebuffer updates -> GL texture (zero-copy only if measured necessary) | per-screen capture rebinding on reload (bug 33) |
| Global hotkeys (Ctrl+Shift+R, Ctrl+Alt+S) | control socket in `$XDG_RUNTIME_DIR` + `rayneo-ctl`, bound in the compositor's key config | Wayland has no global hotkeys for clients |
| Win32 controller | Qt 6 over `rayneo_app_model` | engine command/status protocol unchanged |
| Taskbar auto-hide, window migration, laptop-panel detach (bugs 14-19, 36, 39) | not needed: Windows-specific workarounds | - |

## Linux-specific notes

- `orientation_calibrate`: SIGINT/SIGTERM/SIGHUP take the same cancel path as Ctrl+C on Windows
  (stream off, `failed`/`cancelled`, exit 1). A pipe/FIFO stdin in `--auto` gets the same `q` /
  EOF watcher (bug 27). The default output path is found from `/proc/self/exe` (invariant 7).
- `gt_hid.cpp`: `wchar_t` is UTF-32 on Linux, so HID strings may carry supplementary code points;
  the narrowing now emits 4-byte UTF-8 for them.
- Secure Boot is off on the reference machine, so the evdi DKMS module needs no signing there. On a
  machine with Secure Boot, the module must be enrolled with `mokutil`.
