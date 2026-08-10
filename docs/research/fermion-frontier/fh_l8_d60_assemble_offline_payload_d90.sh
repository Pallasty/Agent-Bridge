#!/bin/sh
set -eu

TARGET=/Data/CascadeProjects/.fh-l8-staging/d90/payload
ROOTFS=/Data/CascadeProjects/.fh-l8-staging/d89/fh-l8-resolute-amd64-minroot.tar.xz
REPO=/Data/CascadeProjects/.ab-worktrees/agent-bridge-fh-l8-d54r-integration
MMC_STABLE=/dev/disk/by-id/mmc-SL64G_0x6ae35823

[ "$(readlink -f "$MMC_STABLE")" = /dev/mmcblk0 ]
if findmnt -rn -S /dev/mmcblk0p1 >/dev/null; then
    echo "refusing assembly: MMC partition is mounted" >&2
    exit 40
fi
if [ -e "$TARGET" ]; then
    echo "refusing assembly: target already exists: $TARGET" >&2
    exit 41
fi
echo '7756c1c849dcf1b7e442d526e18b29a6af9d6601fed0740be294145eadc33889  /Data/CascadeProjects/.fh-l8-staging/d89/fh-l8-resolute-amd64-minroot.tar.xz' | sha256sum -c -

mkdir -p "$TARGET"/boot "$TARGET"/efi/EFI/BOOT "$TARGET"/rootfs \
    "$TARGET"/source "$TARGET"/provenance "$TARGET"/config "$TARGET"/evidence

cp --reflink=auto "$ROOTFS" "$TARGET/rootfs/fh-l8-resolute-amd64-minroot.tar.xz"
install -m 0644 /boot/vmlinuz-7.0.0-29-generic "$TARGET/boot/vmlinuz-7.0.0-29-generic"
install -m 0644 /boot/initrd.img-7.0.0-29-generic "$TARGET/boot/initrd.img-7.0.0-29-generic"
tar -C /usr/lib/modules -cJf "$TARGET/boot/modules-7.0.0-29-generic.tar.xz" 7.0.0-29-generic
install -m 0644 /usr/lib/shim/shimx64.efi.signed.latest "$TARGET/efi/EFI/BOOT/BOOTX64.EFI"
install -m 0644 /usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed "$TARGET/efi/EFI/BOOT/grubx64.efi"

git -C "$REPO" bundle create "$TARGET/source/agent-bridge.bundle" HEAD
cp "$REPO/docs/research/fermion-frontier/fh_l8_d60_offline_rootfs_staging_d89_receipt.json" "$TARGET/provenance/"
cp "$REPO/docs/research/fermion-frontier/fh_l8_d60_privileged_boot_payload_d88r_receipt.json" "$TARGET/provenance/"

cat > "$TARGET/config/grub.cfg.template" <<'EOF'
set timeout=5
menuentry 'FH-L8 isolated measurement root' {
    linux /boot/vmlinuz-7.0.0-29-generic root=UUID=__FH_L8_ROOT_UUID__ ro irqaffinity=0-14 isolcpus=managed_irq,15
    initrd /boot/initrd.img-7.0.0-29-generic
}
EOF
cat > "$TARGET/config/fstab.template" <<'EOF'
UUID=__FH_L8_ROOT_UUID__ / ext4 defaults,noatime 0 1
UUID=__FH_L8_ESP_UUID__ /boot/efi vfat umask=0077 0 1
EOF
cat > "$TARGET/evidence/README" <<'EOF'
This directory is the only persistent evidence destination during FH-L8 measurement.
Do not mount NVMe filesystems or configure NVMe swap/log destinations.
EOF

(
    cd "$TARGET"
    find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
)
chown -R pallasting:pallasting "$TARGET"
touch /tmp/fh-l8-d90-complete
