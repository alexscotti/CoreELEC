#!/bin/sh
# test_symphony_dovi.sh - drive scripts/symphony-dovi (the boot step that finds
# Amlogic's dovi.ko on a USB stick) against fake /storage, /proc/mounts and
# stand-in vfat devices. Run by the package build (python3 + coreutils).
# Amlogic's real module is in no image and no git tree, so the fixtures are
# minimal aarch64 ELF objects built here with the .modinfo the real one has.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
R=$T/r; FAILS=0; N=0
BIN=$T/bin; mkdir -p $BIN
cp "$HERE/scripts/symphony-dovi" $BIN/
export SYMDOVI_ROOT=$R SYMDOVI_NO_SYSTEM=1 SYMDOVI_WAIT=0

ok()  { N=$((N+1)); echo "ok   $N $*"; }
bad() { N=$((N+1)); FAILS=$((FAILS+1)); echo "FAIL $N $*"; }
run() { python3 $BIN/symphony-dovi "$@" > $R/out 2>&1; echo $? > $R/rc; }
has() { grep -q "$1" $R/out && ok "$2" || bad "$2: wanted '$1' in: $(cat $R/out)"; }
no()  { grep -q "$1" $R/out && bad "$2: did NOT want '$1' in: $(cat $R/out)" || ok "$2"; }

# A kernel module is identified by structure, not by name, so the fixtures are
# real ELF64 aarch64 relocatables carrying a .modinfo section.
cat > $T/mkmod.py <<'PY'
import struct, sys

def mod(path, name, desc, vermagic, machine=183, etype=1):
    info = b''.join(b'%s\0' % s.encode() for s in (
        'name=' + name, 'description=' + desc, 'license=AML', 'vermagic=' + vermagic))
    names = b'\0.modinfo\0.shstrtab\0'
    shoff, shentsize, shnum = 64, 64, 3
    data = shoff + shentsize * shnum
    eh = bytearray(64)
    eh[0:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', eh, 16, etype, machine, 1)
    struct.pack_into('<Q', eh, 40, shoff)
    struct.pack_into('<HHH', eh, 58, shentsize, shnum, 2)

    def sh(nameoff, typ, off, size):
        b = bytearray(64)
        struct.pack_into('<II', b, 0, nameoff, typ)
        struct.pack_into('<QQ', b, 24, off, size)
        return bytes(b)

    shdrs = (sh(0, 0, 0, 0)
             + sh(names.index(b'.modinfo'), 1, data, len(info))
             + sh(names.index(b'.shstrtab'), 3, data + len(info), len(names)))
    open(path, 'wb').write(bytes(eh) + shdrs + info + names)

a = sys.argv
mod(a[1], a[2], a[3], a[4], int(a[5]) if len(a) > 5 else 183)
PY
GOOD='5.15.170-android14-11-g7f9c2d1e4b68-dirty SMP preempt mod_unload modversions aarch64'
OLD='5.15.100-android14-11-gdeadbeef SMP preempt mod_unload modversions aarch64'
mkmod() { python3 $T/mkmod.py "$@"; }
good() { mkmod "$1" dovi_gen_5_15_2026 'Amlogic Dolby Vision Driver' "$GOOD"; }

reset() {
  rm -rf $R; mkdir -p $R/storage/.config $R/proc $R/sticks/plain $R/sticks/sym/SYMPHONY $R/var/media
  : > $R/proc/mounts
}
# Stand-in devices: "<dev>=<dir>" pairs symphony-dovi reads in place of
# blkid + mount, in device order.
devs() { export SYMDOVI_DEVS="$1"; }

# --- nothing anywhere
reset; devs ""
run scan
[ "$(cat $R/rc)" = 0 ] && ok "scan exits 0 with no devices" || bad "rc $(cat $R/rc)"
has "no dovi.ko found" "scan says how to provision"
[ -e $R/storage/.config/dovi.ko ] && bad "wrote a module from nowhere" || ok "nothing captured"

# --- the root of a plain FAT32 stick
reset; good $R/sticks/plain/dovi.ko; devs "/dev/sda1=$R/sticks/plain"
run scan
has "captured" "captures from the root of a plain stick"
cmp -s $R/sticks/plain/dovi.ko $R/storage/.config/dovi.ko \
  && ok "captured bytes match the stick" || bad "captured bytes differ"

# --- a stick this step mounts itself is unmounted before the copy: the module
# has to have been read while it was mounted (it failed with ENOENT on the
# first public stick, 2026-10-26)
reset; good $R/sticks/plain/dovi.ko; cp $R/sticks/plain/dovi.ko $T/orig.ko; devs "/dev/sda1=$R/sticks/plain"
SYMDOVI_STUB_UMOUNT=1 run scan
has "captured" "captures from a stick that is unmounted before the copy"
cmp -s $T/orig.ko $R/storage/.config/dovi.ko && ok "the bytes read while mounted are the ones written" || bad "captured bytes differ or are missing: $(cat $R/out)"

# --- SYMPHONY/dovi.ko on the Symphony stick
reset; good $R/sticks/sym/SYMPHONY/dovi.ko; devs "/dev/sdb1=$R/sticks/sym"
run scan
has "SYMPHONY/dovi.ko is dovi_gen" "captures from SYMPHONY/ on the Symphony stick"
[ -s $R/storage/.config/dovi.ko ] && ok "SYMPHONY capture landed" || bad "nothing landed"

# --- SYMPHONY/ wins over the root of the same stick
reset; good $R/sticks/sym/SYMPHONY/dovi.ko
mkmod $R/sticks/sym/dovi.ko dovi_root 'Amlogic Dolby Vision Driver' "$GOOD"
devs "/dev/sdb1=$R/sticks/sym"
run scan
has "SYMPHONY/dovi.ko" "SYMPHONY/ is searched before the stick root"
no "dovi_root" "the root copy was not taken"

# --- already captured: no scan at all
reset; good $R/storage/.config/dovi.ko; good $R/sticks/plain/dovi.ko
devs "/dev/sda1=$R/sticks/plain"
run scan
has "already" "a valid module in place skips the scan"
no "captured" "nothing re-copied"

# --- a module for too old a kernel is rejected, not insmod'd later
reset; mkmod $R/sticks/plain/dovi.ko dovi_gen_5_15_2026 'Amlogic Dolby Vision Driver' "$OLD"
devs "/dev/sda1=$R/sticks/plain"
run scan
has "needs at least 5.15.137" "rejects a module built for an older kernel"
[ -e $R/storage/.config/dovi.ko ] && bad "captured an old module" || ok "old module not captured"

# --- the wrong file under the right name
reset; echo "this is not a kernel module" > $R/sticks/plain/dovi.ko
devs "/dev/sda1=$R/sticks/plain"
run scan
has "not an aarch64 kernel module" "rejects a file that is not a module"
[ -e $R/storage/.config/dovi.ko ] && bad "captured a non-module" || ok "non-module not captured"

# --- some other module named dovi.ko
reset; mkmod $R/sticks/plain/dovi.ko snd_hda_intel 'Intel HDA driver' "$GOOD"
devs "/dev/sda1=$R/sticks/plain"
run scan
has "not the Dolby Vision driver" "rejects an unrelated kernel module"

# --- an x86_64 module (wrong arch: EM_X86_64 = 62)
reset; mkmod $R/sticks/plain/dovi.ko dovi_gen_5_15_2026 'Amlogic Dolby Vision Driver' "$GOOD" 62
devs "/dev/sda1=$R/sticks/plain"
run scan
has "not an aarch64 kernel module" "rejects a module for another architecture"

# --- a truncated download
reset; good $T/whole.ko; head -c 100 $T/whole.ko > $R/sticks/plain/dovi.ko
devs "/dev/sda1=$R/sticks/plain"
run scan
has "not an aarch64 kernel module" "rejects a truncated module"

# --- the partitions behind /flash and /storage are never candidates
reset; good $R/sticks/plain/dovi.ko
printf '/dev/sda1 /flash vfat ro 0 0\n' > $R/proc/mounts
devs "/dev/sda1=$R/sticks/plain"
run scan
has "no dovi.ko found" "skips the partition mounted at /flash"
reset; good $R/sticks/plain/dovi.ko
printf '/dev/mmcblk0p2 /storage ext4 rw 0 0\n/dev/sda1 /flash vfat ro 0 0\n' > $R/proc/mounts
devs "/dev/sda1=$R/sticks/plain"
run scan
has "no dovi.ko found" "skips the partition mounted at /storage"

# --- a stick udevil has ALREADY mounted is read in place, not skipped.
# This is the Symphony stick's normal state by the time this step runs.
reset; good $R/sticks/sym/SYMPHONY/dovi.ko
printf '/dev/sda1 /flash vfat ro 0 0\n/dev/sdb1 /var/media/symphony-usb vfat rw 0 0\n' > $R/proc/mounts
devs "/dev/sda1=$R/sticks/plain,/dev/sdb1=$R/sticks/sym"
run scan
has "captured" "a stick already mounted under /var/media is still searched"
[ -s $R/storage/.config/dovi.ko ] && ok "the module came off the mounted stick" || bad "nothing captured"

# --- the root of the Symphony stick works too, not just SYMPHONY/
reset; good $R/sticks/sym/dovi.ko
printf '/dev/sdb1 /var/media/symphony-usb vfat rw 0 0\n' > $R/proc/mounts
devs "/dev/sdb1=$R/sticks/sym"
run scan
has "captured" "dovi.ko in the root of the Symphony stick is found"

# --- a second device is searched when the first has nothing
reset; good $R/sticks/sym/SYMPHONY/dovi.ko
devs "/dev/sda1=$R/sticks/plain,/dev/sdb1=$R/sticks/sym"
run scan
has "captured" "falls through to the next device"

# --- notify: only when the module actually loaded
reset; good $R/storage/.config/dovi.ko
printf 'dovi 466944 0 - Live 0xffffffc008a00000 (O)\n' > $R/proc/modules
run notify
has "would notify: Driver loaded from the USB stick" "notify names the stick when we captured it"
reset; printf 'dovi 466944 0 - Live 0xffffffc008a00000 (O)\n' > $R/proc/modules
run notify
has "would notify: Driver loaded from the system" "notify says system when the module came from elsewhere"
reset; printf 'snd_hda_intel 1234 0 - Live 0x0\n' > $R/proc/modules
run notify
has "not loaded" "notify is silent when the module did not load"
[ "$(cat $R/rc)" = 0 ] && ok "notify exits 0 with no module" || bad "notify rc $(cat $R/rc)"
reset; : > $R/proc/modules
run notify
has "not loaded" "notify is silent with an empty /proc/modules"
# the toast text must survive Kodi's comma-splitting builtin
reset; good $R/storage/.config/dovi.ko
printf 'dovi_gen 466944 0 - Live 0x0\n' > $R/proc/modules
run notify
grep -q "would notify: Driver loaded from the USB stick$" $R/out \
  && ok "the toast text has no comma" || bad "toast text: $(cat $R/out)"

# --- notify is once per BOOT, not once per Kodi restart
reset; good $R/storage/.config/dovi.ko
printf 'dovi 466944 0 - Live 0x0\n' > $R/proc/modules
run notify
has "would notify" "first notify of the boot speaks"
run notify
has "already notified this boot" "a Kodi restart in the same boot stays quiet"
no "would notify" "no second toast"
[ "$(cat $R/rc)" = 0 ] && ok "the quiet notify exits 0" || bad "rc $(cat $R/rc)"
# /run is tmpfs: the next boot has no marker and speaks again
rm -f $R/run/symphony-dovi.notified
run notify
has "would notify" "the next boot speaks again"

# --- status
reset; good $R/storage/.config/dovi.ko
run status
has "dovi_module=dovi_gen_5_15_2026, kernel 5.15.170" "status names the module"
reset; run status
has "dovi_why=absent" "status says when there is none"

# --- nothing is ever written back to a stick
reset; good $R/sticks/sym/SYMPHONY/dovi.ko
before="$(ls -lR $R/sticks | sha256sum)"
devs "/dev/sdb1=$R/sticks/sym"
run scan
has "captured" "captured from the stick"
[ "$(ls -lR $R/sticks | sha256sum)" = "$before" ] \
  && ok "the sticks were left untouched" || bad "something was written to a stick"
[ -e $R/sticks/sym/dovi.ko ] && bad "a copy appeared in the stick root" || ok "no copy made in the stick root"

echo
[ $FAILS = 0 ] && echo "all $N ok" || echo "$FAILS of $N FAILED"
exit $([ $FAILS = 0 ] && echo 0 || echo 1)
