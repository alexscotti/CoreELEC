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


def bundle(installer=STUB, sha=None, drop=None, payload=b'S' * 300000):
    files = {'kernel.img': b'K' * 1000, 'SYSTEM': payload, 'dovi.ko': b'D' * 100,
             'am9slot.sh': installer}
    man = ('SYMPHONY_VERSION=%s\nBUILD_ID=%s\nCOREELEC_VERSION=cv\nam9slot_sha256=%s\n'
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


def main():
    tmp = tempfile.mkdtemp()
    flash = os.path.join(tmp, 'flash')
    data = os.path.join(tmp, 'storage', 'symphony')
    os.makedirs(flash)
    os.makedirs(data)
    cmdline = os.path.join(tmp, 'cmdline')
    open(cmdline, 'w').write('BOOT_IMAGE=kernel_A.img SYSTEM_IMAGE=SYSTEM_A quiet\n')
    open(os.path.join(flash, 'slot.ini'), 'w').write('ceslot=A\n')
    open(os.path.join(flash, 'SLOT_A.manifest'), 'w').write(
        'SYMPHONY_VERSION=%s\nBUILD_ID=%s\nCOREELEC_VERSION=old\n' % ('c' * 40, 'b' * 40))
    rebooted = os.path.join(tmp, 'rebooted')
    port = free_port()
    env = dict(os.environ, SYM_FLASH=flash, SYM_DATA=data, SYM_CMDLINE=cmdline,
               SYM_PORT=str(port), SYM_REBOOT='touch ' + rebooted)
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
        log = req('/install_log')[1].decode()
        check('== installing into slot B' in log, 'install log served')

        # A bundle whose installer is not the one its MANIFEST names.
        upload(bundle(sha='0' * 64))
        s = install_and_wait()
        check(s.get('state') == 'error' and 'am9slot_sha256' in s.get('error', ''), 'tampered installer refused')
        check(os.path.exists(os.path.join(data, 'upload', 'firmware_slot.tar')), 'failed upload kept for a retry')

        upload(bundle(drop='dovi.ko'))
        s = install_and_wait()
        check(s.get('state') == 'error' and 'not a slot bundle' in s.get('error', ''), 'incomplete bundle refused')

        failing = STUB.replace(b'cp "$2/SYSTEM"', b'echo "am9slot: Kodi is playing - refusing" >&2; exit 1; cp "$2/SYSTEM"')
        upload(bundle(installer=failing))
        s = install_and_wait()
        check(s.get('state') == 'error' and 'Kodi is playing' in s.get('error', ''), 'installer refusal surfaces')

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
