#!/usr/bin/env python3
# Run by the CoreELEC-settings package before it installs symphony-webui, and
# by hand: python3 test_symphony_webui.py. Starts the real server on a free
# port against a fake /flash and drives it over HTTP the way the page does:
# chunked upload (resume, 409, bad names), install (the bundle's own
# installer runs; a mismatched or incomplete bundle is refused), goback,
# reboot. The installer here is a stub - the server's contract is only that
# it runs the bundle's am9slot.sh with "install <dir>".
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, 'scripts', 'symphony-webui')
VER = 'a' * 40
NAME = 'coreelec_20261002000000_%s_aarch64_slot.tar' % VER

fails = 0
n = 0


def check(cond, what):
    global fails, n
    n += 1
    if cond:
        print('ok   %d %s' % (n, what))
    else:
        fails += 1
        print('FAIL %d %s' % (n, what))


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


STUB = b'''#!/bin/sh
echo "== installing into slot B"
cp "$2/SYSTEM" "$SYM_FLASH/SYSTEM_B" || exit 1
cp "$2/MANIFEST" "$SYM_FLASH/SLOT_B.manifest"
echo "ceslot=B" > "$SYM_FLASH/slot.ini"
echo "== slot B verified"
'''


def bundle(installer=STUB, sha=None, drop=None, payload=b'S' * 300000, extra=None):
    files = {'kernel.img': b'K' * 1000, 'SYSTEM': payload, 'am9slot.sh': installer}
    files.update(extra or {})
    man = ('VERSION=%s\nBUILD_ID=%s\nCOREELEC_VERSION=cv\nam9slot_sha256=%s\n'
           % (VER, 'b' * 40, sha or hashlib.sha256(installer).hexdigest())).encode()
    files['MANIFEST'] = man
    if drop:
        del files[drop]
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode='w') as tf:
        for k, v in files.items():
            ti = tarfile.TarInfo(k)
            ti.size = len(v)
            tf.addfile(ti, io.BytesIO(v))
    return bio.getvalue()


def mdns_parser_tests():
    """srv_targets on a hand-built response: a dotted instance name
    (symphony.relay, which avahi cannot resolve), compression pointers, and
    records of other types and other service types mixed in."""
    import importlib.machinery
    import importlib.util
    import struct
    # No bytecode: a scripts/__pycache__/ in the package source breaks the
    # package's own "cp scripts/*" (it did, the first build with this test).
    sys.dont_write_bytecode = True
    loader = importlib.machinery.SourceFileLoader('sw', SERVER)
    w = importlib.util.module_from_spec(importlib.util.spec_from_loader('sw', loader))
    loader.exec_module(w)

    def name(n):
        return b''.join(bytes([len(p)]) + p.encode() for p in n.split('.')) + b'\0'
    stype = '_symphony0._tcp.local'
    # question for the type at offset 12; later names point back into it
    q = name(stype) + struct.pack('>HH', 12, 1)
    ptr_to_type = struct.pack('>H', 0xC000 | 12)
    recs = []
    # SRV for "symphony.relay" - two labels, then a pointer to the type
    owner = bytes([8]) + b'symphony' + bytes([5]) + b'relay' + ptr_to_type
    target = name('symphony-relay-0.local')
    recs.append(owner + struct.pack('>HHIH', 33, 1, 120, 6 + len(target)) + struct.pack('>HHH', 0, 0, 6003) + target)
    # SRV for "diskmgr" whose target is a compression pointer to "...local" of the question
    owner2 = bytes([7]) + b'diskmgr' + ptr_to_type
    target2 = bytes([16]) + b'symphony-disks-0' + struct.pack('>H', 0xC000 | (12 + 1 + 10 + 1 + 4))
    recs.append(owner2 + struct.pack('>HHIH', 33, 1, 120, 6 + len(target2)) + struct.pack('>HHH', 0, 0, 6001) + target2)
    # an A record and an SRV of another service type: ignored
    recs.append(name('symphony-disks-0.local') + struct.pack('>HHIH', 1, 1, 120, 4) + bytes([192, 168, 1, 2]))
    other = name('x._other._tcp.local')
    recs.append(other + struct.pack('>HHIH', 33, 1, 120, 6 + len(target)) + struct.pack('>HHH', 0, 0, 1) + target)
    buf = struct.pack('>HHHHHH', 0, 0x8400, 1, len(recs), 0, 0) + q + b''.join(recs)
    got = w.srv_targets(buf, stype + '.')
    check(got.get('symphony-relay-0.local') == {'symphony.relay'}, 'mDNS: dotted instance resolves to its host (%s)' % got)
    check(got.get('symphony-disks-0.local') == {'diskmgr'}, 'mDNS: compressed target name')
    check(len(got) == 2, 'mDNS: other types and record kinds ignored')
    try:
        loop = struct.pack('>HHHHHH', 0, 0, 0, 1, 0, 0) + struct.pack('>H', 0xC000 | 12)
        w.srv_targets(loop, stype)
        check(False, 'mDNS: compression loop rejected')
    except (ValueError, IndexError, struct.error):
        check(True, 'mDNS: compression loop rejected')


IMAGE_NAME = 'CoreELEC-Amlogic-no.aarch64-22.0-Symphony_20261027-am9pro-usb.img.gz'
# The stub installer also records whether the stick's extension came along.
STUB_X = STUB.replace(b'echo "== slot B verified"',
                      b'[ -f "$2/extra.tar" ] && cp "$2/extra.tar" "$SYM_FLASH/got-extra.tar"\necho "== slot B verified"')


def fat_free_bytes(path):
    """Free space on a FAT16/FAT32 image, counted from its FAT."""
    import struct
    with open(path, 'rb') as f:
        bs = f.read(512)
        bps, spc, rsvd, nfats = struct.unpack('<HBHB', bs[11:17])
        rootent, tot16 = struct.unpack('<HH', bs[17:21]); fatsz16, = struct.unpack('<H', bs[22:24])
        tot32, = struct.unpack('<I', bs[32:36])
        fatsz = fatsz16 or struct.unpack('<I', bs[36:40])[0]
        f.seek(rsvd * bps)
        fat = f.read(fatsz * bps)
    data = rsvd + nfats * fatsz + (-(-rootent * 32 // bps) if fatsz16 else 0)
    clusters = ((tot16 or tot32) - data) // spc
    if fatsz16:
        used = lambda c: struct.unpack_from('<H', fat, c * 2)[0]
    else:
        used = lambda c: struct.unpack_from('<I', fat, c * 4)[0] & 0x0FFFFFFF
    return sum(1 for c in range(2, clusters + 2) if used(c) == 0) * spc * bps


def stick_image(installer=STUB_X, payload=None, extra=b'X' * 5000, drop=None, fat_bits=16):
    """A stick image as am9usb makes one: an MBR, a FAT32 boot partition with
    slot A (kernel_A.img, SYSTEM_A, SLOT_A.manifest, am9slot.sh,
    SLOT_A.extra.tar) beside other boot files, and a Linux partition; gzipped.
    SYSTEM_A is written FRAGMENTED (into the hole a deleted file left), so
    the reader has to follow its cluster chain. fat_bits=16 is what a real
    stick has (CoreELEC's boot partition, type 0x0c but FAT16); 32 too."""
    import gzip
    payload = payload or bytes(range(256)) * 2000          # 512000 bytes, not all zero
    files = {'kernel_A.img': b'K' * 1000, 'am9slot.sh': installer, 'SLOT_A.extra.tar': extra,
             'SLOT_A.manifest': ('VERSION=%s\nBUILD_ID=%s\nCOREELEC_VERSION=cv\nam9slot_sha256=%s\n'
                                 % (VER, 'b' * 40, hashlib.sha256(installer).hexdigest())).encode()}
    if drop:
        del files[drop]
    d = tempfile.mkdtemp()
    fat = os.path.join(d, 'fat.img')
    fat_mb = 40
    subprocess.run(['mkfs.fat', '-F', str(fat_bits), '-s', '1' if fat_bits == 32 else '4', '-n', 'COREELEC',
                    '-C', fat, str(fat_mb * 1024)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def mcopy(name, data):
        src = os.path.join(d, 'src')
        open(src, 'wb').write(data)
        subprocess.run(['mcopy', '-i', fat, src, '::' + name], check=True,
                       env=dict(os.environ, MTOOLS_SKIP_CHECK='1'))
    mcopy('cfgload', b'C' * 3000)
    for k, v in files.items():
        mcopy(k, v)
    # mtools allocates after the last cluster it used, so a hole alone is not
    # reused: fill the disk to just short of what SYSTEM_A needs beyond the
    # hole, free the hole, and SYSTEM_A has to wrap into it - fragmented.
    hole = 100000
    mcopy('hole.bin', b'H' * hole)
    mcopy('dtb.img', b'D' * 84000)
    free = fat_free_bytes(fat)
    mcopy('filler.bin', b'F' * (free - (len(payload) - hole) - 8 * 2048))
    subprocess.run(['mdel', '-i', fat, '::hole.bin'], check=True, env=dict(os.environ, MTOOLS_SKIP_CHECK='1'))
    mcopy('SYSTEM_A', payload)
    fat_bytes = open(fat, 'rb').read()
    start = 2048
    n1 = len(fat_bytes) // 512
    n2 = 2048
    mbr = bytearray(512)
    import struct
    mbr[446:462] = bytes([0, 0, 0, 0, 0x0c, 0, 0, 0]) + struct.pack('<II', start, n1)
    mbr[462:478] = bytes([0, 0, 0, 0, 0x83, 0, 0, 0]) + struct.pack('<II', start + n1, n2)
    mbr[510:512] = b'\x55\xaa'
    raw = bytes(mbr) + b'\0' * (start * 512 - 512) + fat_bytes + b'E' * (n2 * 512)
    return gzip.compress(raw, 1), payload


def main():
    mdns_parser_tests()
    tmp = tempfile.mkdtemp()
    flash = os.path.join(tmp, 'flash')
    data = os.path.join(tmp, 'storage', 'symphony')
    os.makedirs(flash)
    os.makedirs(data)
    cmdline = os.path.join(tmp, 'cmdline')
    open(cmdline, 'w').write('BOOT_IMAGE=kernel_A.img SYSTEM_IMAGE=SYSTEM_A quiet\n')
    open(os.path.join(flash, 'slot.ini'), 'w').write('ceslot=A\n')
    open(os.path.join(flash, 'SLOT_A.manifest'), 'w').write(
        'VERSION=%s\nBUILD_ID=%s\nKODI_COMMIT=%s\nCOREELEC_VERSION=old\n' % ('c' * 40, 'b' * 40, 'e' * 40))
    osrel = os.path.join(tmp, 'os-release')
    open(osrel, 'w').write('VERSION="22.0"\nBUILD_ID="%s"\nKODI_COMMIT="%s"\n' % ('b' * 40, 'e' * 40))
    rebooted = os.path.join(tmp, 'rebooted')
    port = free_port()
    env = dict(os.environ, SYM_FLASH=flash, SYM_DATA=data, SYM_CMDLINE=cmdline,
               SYM_PORT=str(port), SYM_REBOOT='touch ' + rebooted, SYM_NO_MDNS='1',
               SYM_OS_RELEASE=osrel)
    srv = subprocess.Popen([sys.executable, SERVER], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = 'http://127.0.0.1:%d' % port

    def req(path, data=None, headers=None, method=None):
        r = urllib.request.Request(base + path, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(r, timeout=20) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def chunk(name, off, total, body):
        st, b = req('/firmware_chunk', data=body, headers={
            'X-Filename': name, 'X-Offset': str(off), 'X-Total': str(total),
            'Content-Type': 'application/octet-stream'})
        return st, json.loads(b)

    def upload(blob, name=NAME, step=100000):
        off = 0
        while off < len(blob):
            st, j = chunk(name, off, len(blob), blob[off:off + step])
            if st != 200:
                return st, j
            off = j['received']
        return 200, j

    def install_and_wait():
        req('/host_management', data=b'action=update_firmware')
        for _ in range(100):
            s = json.loads(req('/firmware_install_status')[1])
            if s.get('state') in ('done', 'error'):
                return s
            time.sleep(0.1)
        return s

    try:
        for _ in range(50):
            try:
                req('/host_management')
                break
            except OSError:
                time.sleep(0.1)
        st, page = req('/host_management')
        page = page.decode()
        check(st == 200 and 'Running slot:</strong> A' in page, 'page shows running slot A')
        check('No firmware file uploaded' in page, 'page: nothing uploaded')
        fork = '<a href="https://github.com/alexscotti/CoreELEC/commit/%s" target="_blank" rel="noopener">%s</a>' % ('b' * 40, 'b' * 12)
        kodi = '<a href="https://github.com/alexscotti/xbmc/commit/%s" target="_blank" rel="noopener">%s</a>' % ('e' * 40, 'e' * 12)
        check('Fork commit:</strong> %s' % fork in page and 'Kodi commit:</strong> %s' % kodi in page,
              'page: running fork + Kodi commits link to GitHub')
        check('<td>%s</td><td>%s</td></tr>' % (fork, kodi) in page, 'page: slot A row links both commits')

        st, j = chunk('base_1_%s_aarch64.img.gz' % VER, 0, 10, b'x' * 10)
        check(st == 400, 'Pi image name refused')

        b = bundle()
        st, j = chunk(NAME, 0, len(b), b[:100000])
        check(st == 200 and j['received'] == 100000, 'first chunk accepted')
        st, j = chunk(NAME, 0, len(b), b[:100000])
        check(st == 409 and j.get('expected_offset') == 100000, 'retried first chunk -> 409, upload kept')
        st, j = chunk(NAME, 5, len(b), b'x')
        check(st == 409 and j.get('expected_offset') == 100000, 'wrong offset -> 409 with the real one')
        s = json.loads(req('/firmware_chunk_status?filename=' + NAME)[1])
        check(s['received'] == 100000 and not s['complete'], 'chunk_status reports the resume point')
        off = 100000
        while off < len(b):
            st, j = chunk(NAME, off, len(b), b[off:off + 100000])
            off = j['received']
        check(j.get('done') is True, 'upload completes')
        s = json.loads(req('/firmware_chunk_status?filename=' + NAME)[1])
        check(s['complete'] and s['received'] == len(b), 'chunk_status: complete')
        page = req('/host_management')[1].decode()
        check('Install Firmware ' + VER in page, 'page offers Install')

        s = install_and_wait()
        check(s.get('state') == 'done', 'install done (%s)' % s.get('error', ''))
        check(open(os.path.join(flash, 'SYSTEM_B'), 'rb').read() == b'S' * 300000, 'bundle installer ran')
        check(not os.path.exists(os.path.join(data, 'upload', 'firmware_slot.tar')), 'upload removed after install')
        page = req('/host_management')[1].decode()
        check('will be executed on reboot' in page and 'Cancel pending update' in page, 'page: pending switch')
        check('Reboot System to ' + VER in page, 'page: Reboot to new version')
        check('<td>B</td><td>%s</td><td>cv</td><td><a href="https://github.com/alexscotti/CoreELEC/commit/%s"'
              % (VER, 'b' * 40) in page and 'rel="noopener">%s</a></td><td>-</td></tr>' % ('b' * 12) in page,
              'page: slot B from a MANIFEST without KODI_COMMIT shows - for Kodi')
        log = req('/install_log')[1].decode()
        check('== installing into slot B' in log, 'install log served')

        # A bundle whose installer is not the one its MANIFEST names.
        upload(bundle(sha='0' * 64))
        s = install_and_wait()
        check(s.get('state') == 'error' and 'am9slot_sha256' in s.get('error', ''), 'tampered installer refused')
        check(os.path.exists(os.path.join(data, 'upload', 'firmware_slot.tar')), 'failed upload kept for a retry')

        upload(bundle(drop='kernel.img'))
        s = install_and_wait()
        check(s.get('state') == 'error' and 'not a slot bundle' in s.get('error', ''), 'incomplete bundle refused')

        # A bundle built before dovi.ko left the bundle still carries one.
        # It is ignored, not rejected as an unexpected member.
        upload(bundle(extra={'dovi.ko': b'D' * 100}))
        s = install_and_wait()
        check(s.get('state') == 'done', 'a bundle with a legacy dovi.ko still installs')

        # extra.tar (an installer extension) is an optional member.
        upload(bundle(extra={'extra.tar': b'T' * 100}))
        s = install_and_wait()
        check(s.get('state') == 'done', 'bundle with extra.tar accepted (%s)' % s.get('error', ''))
        upload(bundle(extra={'stray.bin': b'x'}))
        s = install_and_wait()
        check(s.get('state') == 'error' and 'stray.bin' in s.get('error', ''), 'other extra members still refused')

        # A stick image, the way the Pi webui takes a full disk image: slot A
        # is read out of its FAT32 partition and installed like a bundle.
        img, payload = stick_image()
        st, j = upload(img, name=IMAGE_NAME)
        check(st == 200 and j.get('done') is True, 'stick image upload accepted (%s)' % j)
        page = req('/host_management')[1].decode()
        check('Install Firmware ' + IMAGE_NAME in page, 'page offers Install for the image, by name')
        s = install_and_wait()
        check(s.get('state') == 'done', 'stick image installs (%s)' % s.get('error', ''))
        check(open(os.path.join(flash, 'SYSTEM_B'), 'rb').read() == payload,
              'SYSTEM taken from the image byte for byte (fragmented on the FAT)')
        check(open(os.path.join(flash, 'got-extra.tar'), 'rb').read() == b'X' * 5000,
              "the stick's SLOT_A.extra.tar arrives as the bundle's extra.tar")
        check(s.get('version') == VER, 'install status names the version from the image manifest')
        check(not os.path.exists(os.path.join(data, 'webstage', '.fat.img')), 'the extracted partition is removed')
        log = req('/install_log')[1].decode()
        check("== reading the stick image's boot partition" in log and '== taking slot A out of it' in log,
              'install log shows the image steps')

        # FAT32 as well (the 0x0c type byte's own meaning).
        img, payload = stick_image(fat_bits=32)
        upload(img, name=IMAGE_NAME)
        s = install_and_wait()
        check(s.get('state') == 'done' and open(os.path.join(flash, 'SYSTEM_B'), 'rb').read() == payload,
              'a FAT32 stick image installs too (%s)' % s.get('error', ''))

        img, _ = stick_image(drop='SLOT_A.manifest')
        upload(img, name=IMAGE_NAME)
        s = install_and_wait()
        check(s.get('state') == 'error' and 'not a Symphony stick image' in s.get('error', ''),
              'an image without slot A is refused (%s)' % s.get('error', ''))

        import gzip as _gz
        upload(_gz.compress(b'not a disk at all' * 100), name=IMAGE_NAME)
        s = install_and_wait()
        check(s.get('state') == 'error' and 'not a disk image' in s.get('error', ''),
              'a .img.gz that is no disk image is refused (%s)' % s.get('error', ''))

        st, j = chunk('CoreELEC-something.img.gz', 0, 10, b'x' * 10)
        check(st == 400, 'an image name without -am9pro-usb is refused')

        failing = STUB.replace(b'cp "$2/SYSTEM"', b'echo "am9slot: Kodi is playing - refusing" >&2; exit 1; cp "$2/SYSTEM"')
        upload(bundle(installer=failing))
        s = install_and_wait()
        check(s.get('state') == 'error' and 'Kodi is playing' in s.get('error', ''), 'installer refusal surfaces')

        # Progress: the target slot already holds an OLD build of the same
        # size (and the same manifest, a reinstall); it must not read as done
        # before the installer has written anything.
        slow = STUB.replace(b'cp "$2/SYSTEM"', b'rm -f "$SYM_FLASH/SLOT_B.manifest"; sleep 2; cp "$2/SYSTEM"')
        sb = bundle(installer=slow)
        upload(sb)
        with tarfile.open(fileobj=io.BytesIO(sb)) as tf:
            open(os.path.join(flash, 'SLOT_B.manifest'), 'wb').write(tf.extractfile('MANIFEST').read())
        open(os.path.join(flash, 'SYSTEM_B'), 'wb').write(b'S' * 300000)
        old = time.time() - 3600
        for f in ('SYSTEM_B', 'SLOT_B.manifest'):
            os.utime(os.path.join(flash, f), (old, old))
        req('/host_management', data=b'action=update_firmware')
        early = None
        for _ in range(60):
            s = json.loads(req('/firmware_install_status')[1])
            if s.get('progress'):
                early = s['progress']
                break
            time.sleep(0.05)
        check(early is not None and early['pos'] == 0 and early['total'] == 1000 + 300000,
              'progress: full total, nothing counted from the old build (%s)' % early)
        for _ in range(100):
            s = json.loads(req('/firmware_install_status')[1])
            if s.get('state') in ('done', 'error'):
                break
            time.sleep(0.1)
        check(s.get('state') == 'done', 'slow install completes')

        # goback runs the stick's /flash/am9slot.sh.
        st, page = req('/host_management', data=b'action=revert_firmware')
        check('no installer on this stick yet' in page.decode(), 'goback without /flash/am9slot.sh explains')
        open(os.path.join(flash, 'am9slot.sh'), 'w').write('echo "== slot.ini -> A"; echo ceslot=A > "$SYM_FLASH/slot.ini"\n')
        req('/host_management', data=b'action=revert_firmware')
        check(open(os.path.join(flash, 'slot.ini')).read().strip() == 'ceslot=A', 'goback ran /flash/am9slot.sh')

        req('/host_management', data=b'action=reboot')
        time.sleep(1.5)
        check(os.path.exists(rebooted), 'reboot runs the reboot command')

        open(cmdline, 'w').write('BOOT_IMAGE=kernel.img quiet\n')
        page = req('/host_management')[1].decode()
        check('without A/B slots' in page, 'plain stick shown as such')
    finally:
        srv.terminate()
        srv.wait()

    print('%d/%d passed' % (n - fails, n))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
