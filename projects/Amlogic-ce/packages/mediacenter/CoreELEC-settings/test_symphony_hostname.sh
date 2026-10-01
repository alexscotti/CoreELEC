#!/bin/sh
# Run by the CoreELEC-settings package before it installs symphony-hostname:
# the channel comes from a SYMPHONY stick, and every way of not having one
# falls back to channel 0.

SCRIPT="$(dirname "$0")/scripts/symphony-hostname"
fails=0

# check <description> <expected hostname> <setup commands, run in the fake root>
check() {
  root="$(mktemp -d)"
  mkdir -p "${root}/flash" "${root}/var/media" "${root}/storage/.cache" \
           "${root}/proc/sys/kernel"
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

[ "${fails}" -eq 0 ] || { echo "symphony-hostname: ${fails} test(s) failed"; exit 1; }
