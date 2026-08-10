#!/bin/sh
set -eu

SOURCE=/Data/CascadeProjects/.fh-l8-staging/d91
TARGET=/Data/CascadeProjects/.fh-l8-staging/d91r5
CFG="$TARGET/grub-embedded.cfg"
ESP="$TARGET/esp"
LOG="$TARGET/uefi-serial.log"

[ ! -e "$TARGET" ] || { echo "refusing existing target: $TARGET" >&2; exit 41; }
[ -f "$SOURCE/rootfs.ext4" ]
[ -f "$SOURCE/esp/boot/vmlinuz-7.0.0-29-generic" ]
[ -f "$SOURCE/esp/boot/initrd.img-7.0.0-29-generic" ]
[ ! -e /run/fh-l8-d82-isolation-transaction.json ]
[ ! -e /sys/fs/cgroup/fh-l8-d60-isolated.slice ]

mkdir -p "$ESP/EFI/BOOT" "$TARGET"
cp --reflink=auto "$SOURCE/rootfs.ext4" "$TARGET/rootfs.ext4"
cp --reflink=auto -a "$SOURCE/esp/boot" "$ESP/"
cp --reflink=auto /usr/share/OVMF/OVMF_VARS_4M.fd "$TARGET/OVMF_VARS_4M.fd"

printf '%s\n' \
  'set timeout=0' \
  'linux (memdisk)/boot/vmlinuz root=/dev/vda rw rd.fstab=0 rd.hostonly=0 rd.luks=0 rd.lvm=0 rd.md=0 rd.dm=0 console=ttyS0 systemd.unit=multi-user.target panic=-1' \
  'initrd (memdisk)/boot/initrd' \
  'boot' > "$CFG"

grub-mkstandalone -O x86_64-efi -o "$ESP/EFI/BOOT/BOOTX64.EFI" \
  "boot/grub/grub.cfg=$CFG" \
  "boot/vmlinuz=$SOURCE/esp/boot/vmlinuz-7.0.0-29-generic" \
  "boot/initrd=$SOURCE/esp/boot/initrd.img-7.0.0-29-generic"
grub-file --is-x86_64-efi "$ESP/EFI/BOOT/BOOTX64.EFI"

timeout 45 qemu-system-x86_64 \
  -machine q35,accel=tcg -m 1024 -smp 2 -nodefaults -no-reboot \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file="$TARGET/OVMF_VARS_4M.fd" \
  -drive if=none,id=rootfs,format=raw,file="$TARGET/rootfs.ext4" \
  -device virtio-blk-pci,drive=rootfs \
  -drive format=raw,file=fat:rw:"$ESP" \
  -serial file:"$LOG" -display none || [ "$?" -eq 124 ]

grep -q 'Welcome to .*Ubuntu 26.04 LTS' "$LOG"
grep -q 'Reached target .*basic.target' "$LOG"
grep -q 'initrd-switch-root.service' "$LOG"
! grep -qi 'kernel panic' "$LOG"
! grep -q 'grub>' "$LOG"
sha256sum "$TARGET/rootfs.ext4" "$TARGET/OVMF_VARS_4M.fd" \
  "$ESP/EFI/BOOT/BOOTX64.EFI" "$CFG" "$LOG"
