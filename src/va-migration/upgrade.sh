#!/bin/bash

# upgrade to another OS
set -x -u

LOG_FILE=/etc/va_upd.log
function diag() {
	local log_content=${@:1}
	echo "INFO $log_content" >> ${LOG_FILE}
}

# Global variables
RUN_DIR="$(dirname $(readlink -f -- "${BASH_SOURCE[0]:-$0}"))"
VMLINUZ="${RUN_DIR}/vmlinuz-convert"
INITRD="${RUN_DIR}/initramfs-convert.img"
UPD="${RUN_DIR}/va.tar.xz"
VADISK="${RUN_DIR}/va.sgdisk"
INITARGS="initrd=initramfs-convert.img rd.retry=20 rescue"
KENREL_VER=

function upd_step1() {
  if [ ! -f "$VMLINUZ" ] || [ ! -f "$INITRD" ] || [ ! -f "$UPD" ]; then
    diag "Upgrade failed, no vmlinuz, initrd or upd"
    return 1
  fi

  # prepare new vmlinuz, initrd, sgdisk, upgrade package
  rm -f /boot/vmlinuz-convert /boot/initramfs-convert.img
  grubby --remove-kernel=/boot/vmlinuz-convert
  mv ${VMLINUZ} /boot/
  mv ${INITRD} /boot/
  mkdir -p /etc/upd/ && rm -rf /etc/upd/*
  mv ${UPD} /etc/upd/
  mv ${VADISK} /etc/upd/
 
  grubby --add-kernel=/boot/vmlinuz-convert --title="VA Upgrade" --initrd=/boot/initramfs-convert.img --args="initrd=initramfs-convert.img rd.retry=20 rescue"
  grubby --set-default /boot/vmlinuz-convert
  reboot
}

function load_upd_files_to_initramfs() {
  lvm vgscan --mknodes
  lvm vgchange -ay

  local rootdev=$(find /dev/mapper/ -name "*root")
  if [ ! -e /dev/sda ] || [  -z "$rootdev" ]; then
    diag "fail to init block"
    return 1
  fi

  mkdir -p /sysimage
  mount "$rootdev" /sysimage
  ret=$?
  diag "mount rootdev ret: $ret"
  if [ $ret -ne 0 ]; then
    return 1
  fi

  # load upd files to memory
  cp -a /sysimage/etc/upd/ /etc/upd
  ret=$?
  umount -l -f /sysimage
  diag "copy upd files ret: $ret"
  return $ret
}

function runCmd() {
  local cmd="$1"
  $cmd >> $LOG_FILE 2>&1
  local ret=$?
  if [ $ret -ne 0 ]; then
    diag "=== run $cmd ret: $ret"
    return 1
  fi
  diag "=== run $cmd succ"
  return 0
}

function init_blk() {
    local vgname=$(lvm vgs  | grep -v '#' | awk '{print $1}')
    local dskname=$(lvm pvs | grep '/dev/' | awk '{print $1}')
    local cmds=(
    "lvm vgchange -an $vgname"
    "lvm pvremove --force --force -y $dskname"
    "sgdisk -Z /dev/sda"
    "sgdisk -l /etc/upd/va.sgdisk /dev/sda"
    'echo 1 > /sys/block/sda/device/rescan'
    "lvm vgcreate VA  /dev/sda3"

    "lvm lvcreate -y -n data -L 512M VA"
    "lvm lvcreate -y -n back -L 512M VA"
    "lvm lvcreate -y -n root -l 100%FREE VA"

    "mkfs.ext4 -F /dev/sda2"
    "mkfs.ext4 -F /dev/mapper/VA-root"
    "mkfs.ext4 -F /dev/mapper/VA-back"
    "mkfs.ext4 -F /dev/mapper/VA-data"
  );

  for cmd in "${cmds[@]}"; do
    runCmd "$cmd"
    if [ $? -ne 0 ]; then
      return 1
    fi
  done
}

function extract_upd() {
  local cmds=(
  'mount /dev/mapper/VA-root /sysimage'
  'mkdir -p /sysimage/boot /sysimage/data'
  'mount    /dev/sda2               /sysimage/boot'
  'mount    /dev/mapper/VA-data   /sysimage/data'
  "tar xf /etc/upd/va.tar.xz --numeric-owner --xattrs --xattrs-include=* -C /sysimage"
  "rm -f /etc/upd/va.tar.xz"
  );

  for cmd in "${cmds[@]}"; do
    runCmd "$cmd"
    if [ $? -ne 0 ]; then
      return 1
    fi
  done
  return 0
}

function install_new_va() {
  local cmds=(
  "umount /sysimage/boot"
  "e2fsck -y -f /dev/sda2"
  "tune2fs -U $(grep UUID /sysimage/etc/fstab | awk '{print $1}' | sed 's/UUID=//') /dev/sda2"
  'mount    /dev/sda2               /sysimage/boot'

  "mount -t proc  /proc /sysimage/proc/"
  "mount -t sysfs /sys  /sysimage/sys/"
  "mount --rbind  /dev  /sysimage/dev/"
  "mount --rbind  /run  /sysimage/run/"

  "cp -a /etc/lvm/backup/VA /sysimage/etc/lvm/backup/"
  "rm -rf /sysimage/etc/lvm/archive/"
  "cp -a /etc/lvm/archive/ /sysimage/etc/lvm/"
  );

  for cmd in "${cmds[@]}"; do
    runCmd "$cmd"
    if [ $? -ne 0 ]; then
      return 1
    fi
  done

  cp -a ${LOG_FILE} /sysimage/etc/upd/upd_step2.log
  ln -s /sysimage/etc/upd/ /etc/upd
  export KENREL_VER=$(ls /sysimage/boot/ | grep vmlinuz-5 | sed 's/vmlinuz-//')
  if [ -z "$KENREL_VER" ] ; then
    diag "failed to get upd kernel version"
    return 1
  fi
  return 0
}

function setgrub() {
  local cmds=(
    'chroot /sysimage /usr/sbin/grub2-install /dev/sda'
    "chroot /sysimage /usr/bin/dracut -f /boot/initramfs-${KENREL_VER}.img ${KENREL_VER}"
  );

  diag "will setup new va kernel: $KENREL_VER"

  for cmd in "${cmds[@]}"; do
    runCmd "$cmd"
    if [ $? -ne 0 ]; then
      return 1
    fi
  done
  
  return 0
}
function upd_step2() {
    diag 'upd_step2 begin'
    load_upd_files_to_initramfs
	init_blk
	extract_upd
	install_new_va
	setgrub
    #reboot #TODO debug
}

function main() {
	grep -q initramfs-convert.img /proc/cmdline
	if [ $? -ne 0 ]; then
		upd_step1
		return
	fi
	upd_step2
}

main
