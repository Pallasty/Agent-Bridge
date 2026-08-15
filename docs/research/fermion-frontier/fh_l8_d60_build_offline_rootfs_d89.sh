#!/bin/sh
set -eu

TARGET=/Data/CascadeProjects/.fh-l8-staging/d89/fh-l8-resolute-amd64-minroot.tar.xz
MMC_STABLE=/dev/disk/by-id/mmc-SL64G_0x6ae35823

[ "$(readlink -f "$MMC_STABLE")" = /dev/mmcblk0 ]
if findmnt -rn -S /dev/mmcblk0p1 >/dev/null; then
    echo "refusing build: MMC partition is mounted" >&2
    exit 40
fi
if [ -e "$TARGET" ]; then
    echo "refusing build: target already exists: $TARGET" >&2
    exit 41
fi

mmdebstrap \
    --mode=root \
    --variant=minbase \
    --format=tar \
    --architectures=amd64 \
    --components=main,universe \
    --include=systemd-sysv,python3-minimal,util-linux,procps,pciutils,kmod,iproute2,e2fsprogs,dosfstools,ca-certificates \
    resolute \
    "$TARGET" \
    http://cn.archive.ubuntu.com/ubuntu

chown pallasting:pallasting "$TARGET"
sha256sum "$TARGET" > /tmp/fh-l8-d89-rootfs-sha256.txt
chmod 0644 /tmp/fh-l8-d89-rootfs-sha256.txt
touch /tmp/fh-l8-d89-complete
