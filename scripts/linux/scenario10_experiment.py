#!/usr/bin/env python3
"""Scenario 10 seed sweep (docs/linux/BASELINE.md, "Scenario 10 is seed-dependent").

Builds an instrumented copy of src/tools/pose_scenarios.cpp in a temporary
directory (the repository is not modified), links it against an existing
build's librayneo_core.a, and runs scenario 10 over many seeds with:
  NOISE=std|portable  std::normal_distribution, or Box-Muller on raw mt19937
                      words (the same sequence under any standard library)
  NOWALK=1            the simulated true bias's random walk switched off

Usage: scripts/linux/scenario10_experiment.py [BUILD_DIR] [SEEDS]
       (defaults: build/linux-gcc, 40)
"""
import os
import statistics
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(REPO, "build", "linux-gcc")
SEEDS = int(sys.argv[2]) if len(sys.argv) > 2 else 40

SHIM = r'''
#include <cstdlib>
#include <random>
#include <cmath>
#include <string>
// EXPERIMENT ONLY: switchable normal generator and scenario 10 seed.
static bool g_portable = std::getenv("NOISE") && std::string(std::getenv("NOISE")) == "portable";
struct ExpNormal {
    std::normal_distribution<float> std_{0.0f, 1.0f};
    float mean = 0.0f, sd = 1.0f;
    bool has_spare = false;
    double spare = 0.0;
    ExpNormal() = default;
    ExpNormal(float m, float s) : std_(m, s), mean(m), sd(s) {}
    template <class G> float operator()(G& g) {
        if (!g_portable) return std_(g);
        if (has_spare) { has_spare = false; return static_cast<float>(mean + sd * spare); }
        const double u1 = (static_cast<double>(g()) + 0.5) / 4294967296.0;
        const double u2 = (static_cast<double>(g()) + 0.5) / 4294967296.0;
        const double r = std::sqrt(-2.0 * std::log(u1));
        spare = r * std::sin(6.283185307179586 * u2);
        has_spare = true;
        return static_cast<float>(mean + sd * r * std::cos(6.283185307179586 * u2));
    }
};
static uint32_t s10_seed() {
    const char* e = std::getenv("S10_SEED");
    return e ? static_cast<uint32_t>(std::strtoul(e, nullptr, 0)) : 0xC0FFEE10u;
}
'''


def patch(source: str) -> str:
    source = source.replace("std::normal_distribution<float>", "ExpNormal")
    make = "        HeadSim sim = make_sim(0xC0FFEE10u, 1.5f);  // bias at the documented band limit\n"
    assert source.count(make) == 1, "scenario 10 setup line changed: update this script"
    source = source.replace(make, make.replace("0xC0FFEE10u", "s10_seed()")
                            + '        if (std::getenv("NOWALK")) { sim.bias_walk_degs = 0.0f; }\n')
    check = '        check(drift < 40.0f, "band-limit bias settles to a bounded offset, no runaway", drift, 40.0f);'
    assert source.count(check) == 1, "scenario 10 check line changed: update this script"
    report = ('        std::printf("  EXP true_bias_norm=%.4f\\n", std::sqrt(sim.bias_pkg_degs.x * sim.bias_pkg_degs.x'
              ' + sim.bias_pkg_degs.y * sim.bias_pkg_degs.y + sim.bias_pkg_degs.z * sim.bias_pkg_degs.z));\n')
    source = source.replace(check, report + check)
    first_namespace = source.index("\nnamespace")
    return source[:first_namespace] + "\n" + SHIM + source[first_namespace:]


def run(binary, env_extra, seed):
    env = dict(os.environ, S10_SEED=str(seed), **env_extra)
    out = subprocess.run([binary], env=env, capture_output=True, text=True).stdout
    drift = norm = None
    for line in out.splitlines():
        if "EXP true_bias_norm=" in line:
            norm = float(line.split("=")[1])
        if "band-limit bias settles" in line:
            drift = float(line.split("measured ")[1].split(",")[0])
    return drift, norm


def main():
    core = os.path.join(BUILD, "librayneo_core.a")
    if not os.path.exists(core):
        sys.exit(f"{core} not found: build the {BUILD} tree first")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "scenario10.cpp")
        with open(os.path.join(REPO, "src", "tools", "pose_scenarios.cpp"), encoding="utf-8") as f:
            patched = patch(f.read())
        with open(src, "w", encoding="utf-8") as f:
            f.write(patched)
        binary = os.path.join(tmp, "scenario10")
        subprocess.run([os.environ.get("CXX", "g++"), "-std=c++20", "-O2", "-g", "-DNDEBUG",
                        "-I", os.path.join(REPO, "src"), src, core, "-o", binary], check=True)
        seeds = [0xC0FFEE10 + i * 7919 for i in range(SEEDS)]
        for label, env in [("std noise, walk on", {"NOISE": "std"}),
                           ("portable noise, walk on", {"NOISE": "portable"}),
                           ("std noise, walk off", {"NOISE": "std", "NOWALK": "1"}),
                           ("portable noise, walk off", {"NOISE": "portable", "NOWALK": "1"})]:
            with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
                results = list(pool.map(lambda s: run(binary, env, s), seeds))
            drifts = sorted(d for d, _ in results)
            fails = sum(d >= 40.0 for d in drifts)
            outside = [(d, n) for d, n in results if n > 1.5]
            fails_outside = sum(d >= 40.0 for d, _ in outside)
            print(f"{label:26s} n={len(drifts)} min={drifts[0]:.2f} median={statistics.median(drifts):.2f} "
                  f"max={drifts[-1]:.2f} mean={statistics.mean(drifts):.2f} fails={fails} "
                  f"| final true |bias| > 1.5: {len(outside)} runs, {fails_outside} of the fails")
        default = run(binary, {"NOISE": "std"}, 0xC0FFEE10)
        print(f"default seed, std noise, walk on: drift {default[0]:.4f} deg, final true |bias| {default[1]:.4f} deg/s")


if __name__ == "__main__":
    main()
