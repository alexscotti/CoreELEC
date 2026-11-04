#!/bin/sh
# Run by the CoreELEC-settings package before it installs symphony-hostname:
# on an A/B slot stick the channel comes from a SYMPHONY stick, and every way
# of not having one falls back to channel 0; on a CoreELEC install updated with
# the tar (no slot on the kernel command line) the hostname is left alone.

SCRIPT="$(dirname "$0")/scripts/symphony-hostname"
fails=0

# check <description> <expected hostname> <setup commands, run in the fake root>
# The fake root boots slot A unless the setup writes its own proc/cmdline.
check() {
  root="$(mktemp -d)"
  mkdir -p "${root}/flash" "${root}/var/media" "${root}/storage/.cache" \
           "${root}/proc/sys/kernel"
  echo "BOOT_IMAGE=kernel_A.img SYSTEM_IMAGE=SYSTEM_A boot=LABEL=COREELEC disk=LABEL=STORAGE" \
    >"${root}/proc/cmdline"
  (cd "${root}" && sh -c "$3")
  SYMPHONY_HOSTNAME_ROOT="${root}" SYMPHONY_HOSTNAME_WAIT=0 \
    sh "${SCRIPT}" >/dev/null
  got_kernel="$(cat "${root}/proc/sys/kernel/hostname" 2>/dev/null)"
  got_cache="$(cat "${root}/storage/.cache/hostname" 2>/dev/null)"
  if [ "${got_kernel}" = "$2" ] && [ "${got_cache}" = "$2" ]; then
    echo "ok   $1"
  else
    echo "FAIL $1: expected $2, got kernel '${got_kernel}' cache '${got_cache}'"
    fails=$((fails + 1))
  fi
  rm -rf "${root}"
}

check "no stick is channel 0" symphony-coreelec-0 ":"
check "a stick's channel" symphony-coreelec-3 \
  "mkdir -p var/media/STICK/SYMPHONY && echo 3 >var/media/STICK/SYMPHONY/channel"
check "the boot stick's own SYMPHONY dir" symphony-coreelec-5 \
  "mkdir -p flash/SYMPHONY && echo 5 >flash/SYMPHONY/channel"
check "a stick with no SYMPHONY dir is no stick" symphony-coreelec-0 \
  "mkdir -p var/media/OTHER && echo 4 >var/media/OTHER/channel"
check "a SYMPHONY dir with no channel file is 0" symphony-coreelec-0 \
  "mkdir -p var/media/STICK/SYMPHONY"
check "a channel that is not one digit is 0" symphony-coreelec-0 \
  "mkdir -p var/media/STICK/SYMPHONY && echo 12 >var/media/STICK/SYMPHONY/channel"
check "an empty channel file is 0" symphony-coreelec-0 \
  "mkdir -p var/media/STICK/SYMPHONY && : >var/media/STICK/SYMPHONY/channel"
check "CRLF and spaces around the digit" symphony-coreelec-7 \
  "mkdir -p var/media/STICK/SYMPHONY && printf ' 7 \r\n' >var/media/STICK/SYMPHONY/channel"
check "replaces the cached CoreELEC name" symphony-coreelec-2 \
  "echo CoreELEC >storage/.cache/hostname && mkdir -p var/media/S/SYMPHONY && echo 2 >var/media/S/SYMPHONY/channel"
check "slot B, CE_FLASH, leading slash" symphony-coreelec-4 \
  "echo 'BOOT_IMAGE=kernel_B.img SYSTEM_IMAGE=/SYSTEM_B boot=LABEL=CE_FLASH' >proc/cmdline && mkdir -p var/media/S/SYMPHONY && echo 4 >var/media/S/SYMPHONY/channel"

# A CoreELEC install updated in place with the tar boots SYSTEM: its own name
# stays, even with a SYMPHONY stick plugged in.
nonslot="echo 'BOOT_IMAGE=kernel.img SYSTEM_IMAGE=SYSTEM boot=LABEL=COREELEC disk=LABEL=STORAGE' >proc/cmdline && echo myhost >storage/.cache/hostname && echo myhost >proc/sys/kernel/hostname"
check "tar install keeps its hostname" myhost "${nonslot}"
check "tar install ignores a SYMPHONY stick" myhost \
  "${nonslot} && mkdir -p var/media/S/SYMPHONY && echo 2 >var/media/S/SYMPHONY/channel"
check "SYSTEM_A only as part of another word is no slot" myhost \
  "${nonslot} && echo 'SYSTEM_IMAGE=SYSTEM X_SYSTEM_IMAGE=SYSTEM_A' >proc/cmdline"
check "no SYSTEM_IMAGE at all is no slot" myhost \
  "${nonslot} && echo 'boot=LABEL=COREELEC' >proc/cmdline"

[ "${fails}" -eq 0 ] || { echo "symphony-hostname: ${fails} test(s) failed"; exit 1; }
