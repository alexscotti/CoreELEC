#!/usr/bin/env python3
"""Tests for symphony-userdata-merge: run it on a fragment dir and a live file."""

import importlib.util
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from importlib.machinery import SourceFileLoader

HERE = os.path.dirname(os.path.abspath(__file__))
loader = SourceFileLoader("sum_", os.path.join(HERE, "symphony-userdata-merge"))
spec = importlib.util.spec_from_loader("sum_", loader)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DEFAULTS = """<settings version="4">
  <setting id="disc.playback">2</setting>
  <setting id="audiooutput.streamsilence">0</setting>
</settings>
"""
THEATER = """<settings version="4">
  <setting id="services.webserver">true</setting>
  <setting id="services.webserverpassword">symphony</setting>
  <settinglevel>3</settinglevel>
</settings>
"""


def run(live_text, fragments=(("10-symphony.xml", DEFAULTS), ("50-theater.xml", THEATER))):
    d = tempfile.mkdtemp()
    fd = os.path.join(d, "guisettings.d")
    os.mkdir(fd)
    for name, text in fragments:
        open(os.path.join(fd, name), "w").write(text)
    lp = os.path.join(d, "userdata", "guisettings.xml")
    if live_text is not None:
        os.mkdir(os.path.dirname(lp))
        open(lp, "w").write(live_text)
    rc = mod.main(fd, lp)
    out = open(lp).read() if os.path.exists(lp) else None
    return rc, out


def settings(text):
    return {s.get("id"): s.text for s in ET.fromstring(text).findall("setting")}


fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# no live file: one is written with every fragment's settings
rc, out = run(None)
s = settings(out) if out else {}
check("absent live file is written", out is not None and rc == 0)
check("written file has the public defaults", s.get("disc.playback") == "2" and s.get("audiooutput.streamsilence") == "0")
check("written file has the theater settings", s.get("services.webserverpassword") == "symphony")
check("written file has settinglevel", out is not None and ET.fromstring(out).findtext("settinglevel") == "3")
check("written file keeps the fragment version", out is not None and ET.fromstring(out).get("version") == "4")

# a public build: only the defaults fragment
rc, out = run(None, fragments=(("10-symphony.xml", DEFAULTS),))
s = settings(out)
check("public build writes only the defaults", set(s) == {"disc.playback", "audiooutput.streamsilence"})

# a reset profile: Kodi's bare file gets every one of ours back
rc, out = run('<settings version="2">\n</settings>\n')
s = settings(out)
check("reset profile regains the defaults", s.get("disc.playback") == "2")
check("reset profile regains the webserver", s.get("services.webserver") == "true")
check("settinglevel is not merged into an existing file", ET.fromstring(out).find("settinglevel") is None)

# a box setting is never overwritten, not even one set back to Kodi's default
rc, out = run('<settings version="2">\n'
              '  <setting id="services.webserverpassword">mine</setting>\n'
              '  <setting id="disc.playback" default="true">0</setting>\n'
              '</settings>\n')
s = settings(out)
check("existing password kept", s.get("services.webserverpassword") == "mine")
check("existing default-valued setting kept", s.get("disc.playback") == "0")
check("still adds what is missing", s.get("audiooutput.streamsilence") == "0")

# nothing missing: the file is left exactly as it was
full = ('<settings version="2">\n'
        '  <setting id="disc.playback">2</setting>\n'
        '  <setting id="audiooutput.streamsilence">0</setting>\n'
        '  <setting id="services.webserver">true</setting>\n'
        '  <setting id="services.webserverpassword">symphony</setting>\n'
        '</settings>\n')
rc, out = run(full)
check("untouched when complete", out == full)

# a later fragment wins for an id both carry
rc, out = run(None, fragments=(("10-symphony.xml", DEFAULTS),
                               ("50-theater.xml", '<settings version="4"><setting id="disc.playback">1</setting></settings>')))
check("later fragment wins", settings(out).get("disc.playback") == "1")

# an unparseable live file is left alone
rc, out = run('<settings version="2">\n  <setting id="x">')
check("truncated live file untouched", out == '<settings version="2">\n  <setting id="x">' and rc == 0)

# no fragments at all: nothing is written
rc, out = run(None, fragments=())
check("no fragments, no file", out is None and rc == 0)

print(("FAILED: " + ", ".join(fails)) if fails else "all ok")
sys.exit(1 if fails else 0)
