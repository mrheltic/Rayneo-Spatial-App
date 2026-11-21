#!/usr/bin/env bash
# Development environment for the Linux port (Ubuntu/Debian).
#
#   sudo scripts/linux/setup-dev.sh            # phase 1-2: core, tests, renderer
#   sudo scripts/linux/setup-dev.sh --evdi     # + phase 3: virtual displays (DKMS module)
#   sudo scripts/linux/setup-dev.sh --qt       # + phase 4: Qt 6 controller
#
# Installs distribution packages and the udev rule for the glasses. Touches
# nothing else; safe to re-run.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "run with sudo: sudo $0 $*" >&2
  exit 1
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "${here}/../.." && pwd)"

packages=(
  build-essential cmake ninja-build pkg-config git clang
  libhidapi-dev nlohmann-json3-dev
  libegl-dev libgles-dev libdrm-dev libgbm-dev
  libwayland-dev wayland-protocols libxkbcommon-dev
  libpipewire-0.3-dev libspa-0.2-dev
)
for arg in "$@"; do
  case "${arg}" in
    --evdi) packages+=(evdi-dkms libevdi-dev "linux-headers-$(uname -r)") ;;
    --qt)   packages+=(qt6-base-dev qt6-declarative-dev) ;;
    *) echo "unknown option: ${arg}" >&2; exit 2 ;;
  esac
done

apt-get update
apt-get install -y --no-install-recommends "${packages[@]}"

install -m 0644 "${repo}/packaging/linux/udev/70-rayneo-gt.rules" /etc/udev/rules.d/70-rayneo-gt.rules
udevadm control --reload
udevadm trigger --subsystem-match=hidraw

echo
echo "done. Reconnect the glasses, then (as your normal user):"
echo "  cmake --preset linux-gcc && cmake --build --preset linux-gcc && ctest --preset linux-gcc"
if [[ " $* " == *" --evdi "* ]]; then
  echo "evdi: check 'dkms status' lists evdi as installed for $(uname -r)"
fi
