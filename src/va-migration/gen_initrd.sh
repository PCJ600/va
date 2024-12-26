#!/bin/bash

set -u -x

ROOT_DIR="$(dirname $(readlink -f -- "${BASH_SOURCE[0]:-$0}"))"
RESOURCES_DIR=${ROOT_DIR}/resources
OUTPUT_DIR=${ROOT_DIR}/output/img
DESTDIR=${OUTPUT_DIR}/rootfs_cpio

verbose="y"
# $1 = file type (for logging)
# $2 = file to copy to initramfs
# $3 (optional) Name for the file on the initramfs
# Location of the image dir is assumed to be $DESTDIR
# If the target exists, we leave it and return 1.
# On any other error, we return >1.
copy_file() {
  local type src target link_target

  type="${1}"
  src="${2}"
  target="${3:-$2}"

  [ -f "${src}" ] || return 2

  if [ -d "${DESTDIR}/${target}" ]; then
    target="${target}/${src##*/}"
  fi

  # Canonicalise usr-merged target directories
  case "${target}" in
    /bin/* | /lib* | /sbin/*) target="/usr${target}" ;;
  esac

  # check if already copied
  [ -e "${DESTDIR}/${target}" ] && return 1

  mkdir -p "${DESTDIR}/${target%/*}"

  if [ -h "${src}" ]; then
    # We don't need to replicate a chain of links completely;
    # just link directly to the ultimate target
    link_target="$(readlink -f "${src}")" || return $(($? + 1))

    # Update source for the copy
    src="${link_target}"

    # Canonicalise usr-merged target directories
    case "${link_target}" in
      /bin/* | /lib* | /sbin/*) link_target="/usr${link_target}" ;;
    esac

    if [ "${link_target}" != "${target}" ]; then
      [ "${verbose?}" = "y" ] && echo "Adding ${type}-link ${target}"

      # Create a relative link so it always points
      # to the right place
      ln -rs "${DESTDIR}/${link_target}" "${DESTDIR}/${target}"
    fi
    # Copy the link target if it doesn't already exist
    target="${link_target}"
    [ -e "${DESTDIR}/${target}" ] && return 0
    mkdir -p "${DESTDIR}/${target%/*}"
  fi

  [ "${verbose}" = "y" ] && echo "Adding ${type} ${src}"

  cp -pP "${src}" "${DESTDIR}/${target}" || return $(($? + 1))
}

copy_libgcc() {
  local libdir library

  libdir="$1"
  for library in "${libdir}"/libgcc_s.so.[1-9]; do
    copy_exec "${library}" || return
  done
}

# $1 = executable/shared library to copy to initramfs, with dependencies
# $2 (optional) Name for the file on the initramfs
# Location of the image dir is assumed to be $DESTDIR
# We never overwrite the target if it exists.
copy_exec() {
  local src target x nonoptlib ret

  src="${1}"
  target="${2:-$1}"

  copy_file binary "${src}" "${target}" || return $(($? - 1))

  # Copy the dependant libraries
  for x in $(env --unset=LD_PRELOAD ldd "${src}" 2>/dev/null | sed -e '
                /\//!d;
                /linux-gate/d;
                /=>/ {s/.*=>[[:blank:]]*\([^[:blank:]]*\).*/\1/};
                s/[[:blank:]]*\([^[:blank:]]*\) (.*)/\1/' 2>/dev/null); do

    # Try to use non-optimised libraries where possible.
    # We assume that all HWCAP libraries will be in tls,
    # sse2, vfp or neon.
    nonoptlib=$(echo "${x}" | sed -e 's#/lib/\([^/]*/\)\?\(tls\|i686\|sse2\|neon\|vfp\).*/\(lib.*\)#/lib/\1\3#')
    nonoptlib=$(echo "${nonoptlib}" | sed -e 's#-linux-gnu/\(tls\|i686\|sse2\|neon\|vfp\).*/\(lib.*\)#-linux-gnu/\2#')

    if [ -e "${nonoptlib}" ]; then
      x="${nonoptlib}"
    fi

    # Handle common dlopen() dependency (Debian bug #950254)
    case "${x}" in
      */libpthread.so.*)
        copy_libgcc "${x%/*}" || return
        ;;
    esac

    copy_file binary "${x}" || {
      ret=$?
      [ ${ret} = 1 ] || return $((ret - 1))
    }
  done
}

function extract_initramfs() {
	export XZ_OPT='-T0 -6'
	mkdir -p ${OUTPUT_DIR}/rootfs_cpio && rm -rf ${OUTPUT_DIR}/rootfs_cpio/*
	cd ${OUTPUT_DIR}/rootfs_cpio
	xz -dc ${RESOURCES_DIR}/initramfs-iso.img | cpio -id
}

function modify_initramfs() {
	cp -a ${ROOT_DIR}/upgrade.sh ${DESTDIR}/sbin/
	chmod 777 ${DESTDIR}/sbin/upgrade.sh
	
	cd ${DESTDIR}
	copy_exec /usr/sbin/tune2fs /sbin
	copy_exec /usr/sbin/mkfs.ext4 /sbin
	copy_exec /usr/sbin/sgdisk /sbin

	# sed -i 's/= 4/= 1/g' etc/lvm/lvm.conf
    # cp /etc/e2fsck.conf ./etc/e2fsck.conf
    cp /etc/mke2fs.conf ./etc/mke2fs.conf
	cp -a ${RESOURCES_DIR}/dracut-emergency.service ${DESTDIR}/usr/lib/systemd/system/dracut-emergency.service
}

function repack_initramfs() {
	cd ${DESTDIR}
	find . | cpio -c -o | xz -9 --format=lzma >/tmp/initramfs-convert.img
	cp -a /tmp/initramfs-convert.img ${OUTPUT_DIR}/
}

function gen_initramfs() {
	# prepare vmlinuz
	mkdir -p ${OUTPUT_DIR} && rm -rf ${OUTPUT_DIR}/*
	cp -a ${RESOURCES_DIR}/vmlinuz-iso ${OUTPUT_DIR}/vmlinuz-convert
	# prepare initrd
	extract_initramfs
	modify_initramfs
	repack_initramfs
}

gen_initramfs
