#!/usr/bin/env python3
"""Tests for symphony-userdata-merge: run it with the two files as arguments."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader("sum_", os.path.join(HERE, "symphony-userdata-merge"))
spec = importlib.util.spec_from_loader("sum_", loader)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SHIPPED = """<settings version="2">
  <setting id="services.webserver">true</setting>
  <setting id="services.webserverpassword">symphony</setting>
  <setting id="videoscreen.whitelist">1920x1080p</setting>
</settings>
"""

def run(live_text, shipped_text=SHIPPED):
    d = tempfile.mkdtemp()
    sp = os.path.join(d, "shipped.xml"); open(sp, "w").write(shipped_text)
    lp = os.path.join(d, "live.xml")
    if live_text is not None:
        open(lp, "w").write(live_text)
    rc = mod.main(sp, lp)
    out = open(lp).read() if os.path.exists(lp) else None
    return rc, out

def settings(text):
    return {s.get("id"): s.text for s in ET.fromstring(text).findall("setting")}

fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)

# a reset profile: Kodi's bare file gets every one of ours back
rc, out = run('<settings version="2">\n</settings>\n')
s = settings(out)
check("reset profile regains the webserver", s.get("services.webserver") == "true")
check("reset profile regains the password", s.get("services.webserverpassword") == "symphony")
check("reset profile regains the whitelist", s.get("videoscreen.whitelist") == "1920x1080p")

# a box setting is never overwritten, not even one set back to Kodi's default
rc, out = run('<settings version="2">\n'
              '  <setting id="services.webserverpassword">mine</setting>\n'
              '  <setting id="services.webserver" default="true">false</setting>\n'
              '</settings>\n')
s = settings(out)
check("existing password kept", s.get("services.webserverpassword") == "mine")
check("existing default-valued setting kept", s.get("services.webserver") == "false")
check("still adds what is missing", s.get("videoscreen.whitelist") == "1920x1080p")

# nothing missing: the file is left exactly as it was
full = ('<settings version="2">\n'
        '  <setting id="services.webserver">true</setting>\n'
        '  <setting id="services.webserverpassword">symphony</setting>\n'
        '  <setting id="videoscreen.whitelist">1920x1080p</setting>\n'
        '</settings>\n')
rc, out = run(full)
check("untouched when complete", out == full)

# no live file at all: the plain cp handles that case, we must not create one
rc, out = run(None)
check("absent live file is left absent", out is None and rc == 0)

# an unparseable live file is left alone
rc, out = run('<settings version="2">\n  <setting id="x">')
check("truncated live file untouched", out == '<settings version="2">\n  <setting id="x">' and rc == 0)

print(("FAILED: " + ", ".join(fails)) if fails else "all ok")
sys.exit(1 if fails else 0)
