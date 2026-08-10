#!/bin/sh
set -eu

MMC_STABLE=/dev/disk/by-id/mmc-SL64G_0x6ae35823
[ "$(readlink -f "$MMC_STABLE")" = /dev/mmcblk0 ]
if findmnt -rn -S /dev/mmcblk0p1 >/dev/null; then
    echo "refusing package preparation: MMC partition is mounted" >&2
    exit 40
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-system-x86 ovmf mtools
touch /tmp/fh-l8-d91-packages-complete
