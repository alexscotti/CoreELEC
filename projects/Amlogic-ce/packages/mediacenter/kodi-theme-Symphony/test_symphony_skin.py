#!/usr/bin/env python3
"""Tests for symphony_skin.py: the build of skin.estuary.symphony from the
image's own Estuary. Run by the kodi-theme-Symphony package before it builds
the skin, so a failing test fails the image build.

The rules that matter, and that this file pins down:
  - the patch moves every stock control, adds nothing else, and slides the top
    overlay DOWN and the seek bar UP
  - inset 0 is the stock layout
  - a stock skin the patch no longer fits is refused, never half-patched
  - the home screen is the Symphony background, the clock and Settings
  - Settings keeps three tiles, or stays stock if Estuary reshaped it

The runtime half (inset_for, aspect_label, quoting) is tested beside the
player.coreelec driver, theater mach/base/test_kodi_skin.py.

Run with: python3 test_symphony_skin.py
"""

import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import symphony_skin as ks  # noqa: E402

ADDON = b"""<?xml version="1.0" encoding="UTF-8"?>
<addon id="skin.estuary" version="4.1.0" name="Estuary" provider-name="x">
  <requires><import addon="xbmc.gui" version="5.18.0"/></requires>
</addon>"""

WINDOW = b"""<?xml version="1.0" encoding="UTF-8"?>
<window>
  <visible>Player.Seeking</visible>
  <include>Animation_BottomSlide</include>
  <controls>
    <!-- stock comment -->
    <include>PVRChannelNumberInput</include>
    <control type="group" id="1"><bottom>0</bottom><height>190</height></control>
    <control type="label" id="2"><label>$VAR[SeekLabel] &amp; more</label></control>
    <control type="group" id="3">
      <animation effect="slide" start="0,0" end="0,-80" time="300" condition="Player.Paused">Conditional</animation>
      <animation effect="slide" end="0,-20" time="150" condition="X">conditional</animation>
      <animation effect="slide" end="90,0" time="0" condition="Y">conditional</animation>
      <animation effect="slide" start="0,-200" end="0,0" time="300">VisibleChange</animation>
      <animation effect="slide" start="0,0" end="0,-80" time="300" condition="Player.Paused + Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(1109_topbaroverlay),5)">Conditional</animation>
    </control>
  </controls>
</window>"""


VARIABLES = """<?xml version="1.0" encoding="UTF-8"?>
<includes>
  <variable name="MediaVideoPropVar">
    <value condition="Window.IsActive(fullscreenvideo)">$INFO[VideoPlayer.VideoResolution]$VAR[VideoCodecVar, &#8226; ]$INFO[VideoPlayer.VideoAspect, &#8226; ,:1]</value>
    <value>$INFO[ListItem.VideoResolution]$INFO[ListItem.VideoAspect, &#8226; ,:1]</value>
  </variable>
  <variable name="MediaAudioPropVar">
    <value condition="Window.IsActive(fullscreenvideo)">$VAR[AudioCodecFlagVar]</value>
    <value>$VAR[AudioCodecFlagVar]</value>
  </variable>
  <variable name="Other"><value>$INFO[VideoPlayer.VideoAspect, &#8226; ,:1]</value></variable>
</includes>""".encode()


# Estuary's Settings window, trimmed to its shape: two tile panels with a
# caption between them, the CoreELEC tile last and conditional.
SETTINGS = b"""<?xml version="1.0" encoding="UTF-8"?>
<window>
  <defaultcontrol>9000</defaultcontrol>
  <controls>
    <control type="group">
      <control type="label"><top>420</top><label>$LOCALIZE[5]</label></control>
      <control type="panel" id="9000">
        <onup>Control.SetFocus(9001,0,absolute)</onup>
        <ondown>Control.SetFocus(9001,0,absolute)</ondown>
        <content>
          <item><label>$LOCALIZE[10003]</label><onclick>ActivateWindow(filemanager)</onclick></item>
          <item><label>$LOCALIZE[138]</label><onclick>ActivateWindow(systeminfo)</onclick></item>
          <item><label>$LOCALIZE[31067]</label><onclick>ActivateWindow(eventlog)</onclick></item>
        </content>
      </control>
      <control type="panel" id="9001">
        <content>
          <item><label>$LOCALIZE[14200]</label><onclick>ActivateWindow(PlayerSettings)</onclick></item>
          <item><label>$LOCALIZE[13000]</label><onclick>ActivateWindow(SystemSettings)</onclick></item>
          <item><label>CoreELEC</label><onclick>RunAddon(service.coreelec.settings)</onclick><visible>System.AddonIsEnabled(service.coreelec.settings)</visible></item>
        </content>
      </control>
    </control>
  </controls>
</window>"""


def _stock():
    return {"addon.xml": ADDON, "xml/Variables.xml": VARIABLES,
            "xml/Settings.xml": SETTINGS,
            "xml/Custom_1109_TopBarOverlay.xml": WINDOW,
            "xml/DialogSeekBar.xml": WINDOW,
            "xml/DialogNotification.xml": WINDOW,
            "xml/DialogSelect.xml": WINDOW}


def _anims(root):
    wrapper = root.find("controls")[0]
    return [a for a in wrapper.findall("animation")]


def test_patch_moves_every_control():
    root = ET.fromstring(ks.patch_window(WINDOW, -1))
    controls = root.find("controls")
    if len(controls) != 1 or controls[0].get("type") != "group":
        return False
    moved = [c for c in controls[0] if c.tag not in ("animation", "visible")
             and c.tag is not ET.Comment]
    tags = [(c.tag, c.get("id")) for c in moved]
    return tags == [("include", None), ("control", "1"), ("control", "2"),
                    ("control", "3")]


def test_patch_keeps_window_level_elements_and_text():
    root = ET.fromstring(ks.patch_window(WINDOW, -1))
    label = root.find(".//control[@id='2']/label").text
    return (root.find("visible").text == "Player.Seeking"
            and root.find("include").text == "Animation_BottomSlide"
            and label == "$VAR[SeekLabel] & more")


def test_patch_directions():
    top = _anims(ET.fromstring(ks.patch_window(WINDOW, +1)))
    bottom = _anims(ET.fromstring(ks.patch_window(WINDOW, -1)))

    def end_for(anims, v):
        cond = "String.IsEqual(Skin.String(symphony_inset),%d)" % v
        return next(a.get("end") for a in anims if a.get("condition") == cond)
    return (end_for(top, 140) == "0,140" and end_for(bottom, 140) == "0,-140"
            and all(a.text == "Conditional" and a.get("time") == "0"
                    for a in top + bottom))


def test_patch_has_no_zero_condition():
    """0 = stock layout: no animation may be active then."""
    anims = _anims(ET.fromstring(ks.patch_window(WINDOW, +1)))
    return (not any(a.get("condition").endswith(",0)") for a in anims)
            and len(anims) == ks.INSET_MAX // ks.INSET_STEP)


def test_patch_refuses_other_shapes():
    bad = [b"<window><controls/></window>",
           b"<window><visible>x</visible></window>",
           b"<includes><controls><control/></controls></includes>",
           b"<window><controls>"]
    for data in bad:
        try:
            ks.patch_window(data, +1)
            return False
        except ks.SkinPatchError:
            pass
    return True


def test_addon_renamed():
    root = ET.fromstring(ks.patch_addon_xml(ADDON))
    return (root.get("id") == "skin.estuary.symphony"
            and root.get("name") == "Estuary (Symphony)"
            and root.get("version") == "4.1.0"
            and root.find("requires/import").get("version") == "5.18.0")


def test_addon_must_be_stock_estuary():
    try:
        ks.patch_addon_xml(ADDON.replace(b'id="skin.estuary"', b'id="skin.other"'))
        return False
    except ks.SkinPatchError:
        return True


def test_directions_per_window():
    """Top bar and notification move DOWN, the seek bar UP."""
    files = ks.build(_stock())

    def end140(path):
        cond = "String.IsEqual(Skin.String(symphony_inset),140)"
        return next(a.get("end") for a in _anims(ET.fromstring(files[path]))
                    if a.get("condition") == cond)
    return (end140("xml/Custom_1109_TopBarOverlay.xml") == "0,140"
            and end140("xml/DialogNotification.xml") == "0,140"
            and end140("xml/DialogSeekBar.xml") == "0,-140")


def _stock_anims(data):
    return [(a.get("end"), a.text) for a in
            ET.fromstring(data).find(".//control[@id='3']").findall("animation")]


def test_hide_slides_travel_the_inset():
    """Estuary's own paused tuck (up 80) must still clear the screen once the
    bar has been moved down by the inset -- on the rig it stopped half way,
    behind the masking."""
    top = _stock_anims(ks.patch_window(WINDOW, +1))
    return top == [("0,-380", "Conditional"), ("0,-320", "conditional"),
                   ("90,0", "conditional"), ("0,0", "VisibleChange")]


def test_paused_tuck_removed():
    """The bar stays on screen while paused: Estuary's 5-second tuck is gone
    from every patched window, and nothing else went with it."""
    for d in (+1, -1):
        out = ks.patch_window(WINDOW, d)
        if b"1109_topbaroverlay" in out:
            return False
        if len(_stock_anims(out)) != 4:
            return False
    return True


def test_wrapper_repeats_window_conditions():
    """Everything vanishes the instant the window starts closing: the wrapper
    carries the window's own <visible> conditions, and a window with none
    (the notification, opened by code) gets none."""
    root = ET.fromstring(ks.patch_window(WINDOW, -1))
    wrapper = root.find("controls")[0]
    bare = b"<window><controls><control type='label'/></controls></window>"
    none = ET.fromstring(ks.patch_window(bare, +1)).find("controls")[0]
    return ([v.text for v in wrapper.findall("visible")] == ["Player.Seeking"]
            and root.find("visible").text == "Player.Seeking"
            and none.findall("visible") == [])


def test_inward_slides_untouched():
    """For a bottom window 'outward' is DOWN: an upward conditional slide
    (DialogSeekBar's LiveTV nudge) and the rest are left alone."""
    bottom = _stock_anims(ks.patch_window(WINDOW, -1))
    return bottom == [("0,-80", "Conditional"), ("0,-20", "conditional"),
                      ("90,0", "conditional"), ("0,0", "VisibleChange")]


def test_select_dialog_fits_the_picture():
    """The stream lists are shrunk, not moved: scale = picture / frame height,
    about the screen centre, and only while a film is playing."""
    files = ks.build(_stock())
    anims = _anims(ET.fromstring(files["xml/DialogSelect.xml"]))
    a140 = next(a for a in anims if a.get("condition").endswith(",140)"))
    return (all(a.get("effect") == "zoom" for a in anims)
            and a140.get("end") == "74.07"
            and a140.get("center") == "960,540"
            and a140.get("condition").startswith("Player.HasVideo + "))


def test_info_panel_removed():
    """The poster/plot panel goes from the seek bar window only; every other
    control stays, and other windows keep a control with the same marker."""
    marked = WINDOW.replace(
        b'<control type="label" id="2">',
        b'<control type="group" id="9"><control type="image"><texture>$VAR[NowPlayingPosterVar]</texture></control></control>\n    <control type="label" id="2">')
    stock = _stock()
    stock["xml/DialogSeekBar.xml"] = marked
    stock["xml/DialogNotification.xml"] = marked
    files = ks.build(stock)
    seek = ET.fromstring(files["xml/DialogSeekBar.xml"])
    note = ET.fromstring(files["xml/DialogNotification.xml"])
    return (seek.find(".//control[@id='9']") is None
            and seek.find(".//control[@id='2']") is not None
            and seek.find(".//control[@id='1']") is not None
            and note.find(".//control[@id='9']") is not None)


def test_file_name_title_replaced():
    """The info screen's title label (the file name, for our discs) shows the
    database title string instead -- in the top bar only; the chapter label
    beside it is untouched."""
    titled = WINDOW.replace(
        b'<control type="label" id="2">',
        b'<control type="group" id="8"><control type="label" id="81"><label>$VAR[NowPlayingBreadcrumbsVar]</label></control>'
        b'<control type="label" id="82"><label>$VAR[OSDSubLabelVar]</label></control></control>\n    <control type="label" id="2">')
    stock = _stock()
    stock["xml/Custom_1109_TopBarOverlay.xml"] = titled
    stock["xml/DialogSeekBar.xml"] = titled
    files = ks.build(stock)
    top = ET.fromstring(files["xml/Custom_1109_TopBarOverlay.xml"])
    seek = ET.fromstring(files["xml/DialogSeekBar.xml"])
    return (top.find(".//control[@id='81']/label").text
            == "$INFO[Skin.String(symphony_title)]"
            and top.find(".//control[@id='82']/label").text == "$VAR[OSDSubLabelVar]"
            and seek.find(".//control[@id='81']/label").text
            == "$VAR[NowPlayingBreadcrumbsVar]")


def test_format_line_aspect():
    """The playing film's format line shows OUR aspect string; the library
    (ListItem) value and every other variable are untouched."""
    files = ks.build(_stock())
    root = ET.fromstring(files["xml/Variables.xml"])
    media = root.find("variable[@name='MediaVideoPropVar']").findall("value")
    other = root.find("variable[@name='Other']/value").text
    return ("$INFO[Skin.String(symphony_aspect), \u2022 ]" in media[0].text
            and "VideoPlayer.VideoAspect" not in media[0].text
            and "ListItem.VideoAspect" in media[1].text
            and "VideoPlayer.VideoAspect" in other)


def test_live_bitrates():
    """While a film plays, the video and audio halves of the format line end
    in the live bitrates; the library values do not."""
    files = ks.build(_stock())
    root = ET.fromstring(files["xml/Variables.xml"])
    v = root.find("variable[@name='MediaVideoPropVar']").findall("value")
    a = root.find("variable[@name='MediaAudioPropVar']").findall("value")
    return (v[0].text.endswith("$INFO[Player.Process(videolivebitrate), \u2022 ]")
            and "livebitrate" not in v[1].text
            and a[0].text.endswith("$INFO[Player.Process(audiolivebitrate), \u2022 ]")
            and "livebitrate" not in a[1].text)


def test_osd_window():
    """Symphony's OSD window: shown exactly while symphony_osd is non-empty,
    one label showing it, and inset like the top bar."""
    files = ks.build(_stock())
    root = ET.fromstring(files["xml/Custom_1190_SymphonyOSD.xml"])
    wrapper = root.find("controls")[0]
    label = root.find(".//control[@type='label']/label").text
    down140 = [a for a in _anims(root)
               if a.get("condition").endswith(",140)")][0].get("end")
    return (root.get("id") == "1190" and root.get("type") == "dialog"
            and root.find("visible").text == "!String.IsEmpty(Skin.String(symphony_osd))"
            and [v.text for v in wrapper.findall("visible")]
            == ["!String.IsEmpty(Skin.String(symphony_osd))"]
            and label == "$INFO[Skin.String(symphony_osd)]"
            and down140 == "0,140")


def test_home_is_background_clock_and_settings():
    """Home: the GUI's menu background full screen (shipped in the skin), the
    clock, and one settings button that always has focus and opens Settings.
    Nothing else."""
    files = ks.build(_stock())
    root = ET.fromstring(files["xml/Home.xml"])
    ctls = list(root.find("controls"))
    img = ctls[0]
    incs = list(root.iter("include"))
    params = {p.get("name"): p.get("value") for p in incs[0].iter("param")} \
        if len(incs) == 1 else {}
    labels = [c.findtext("label") for c in root.iter("control")
              if c.get("type") == "label"]
    dc = root.find("defaultcontrol")
    return (len(ctls) == 3
            and img.get("type") == "image"
            and img.findtext("texture") == "special://skin/media/symphony_home.png"
            and files["media/symphony_home.png"][:8] == b"\x89PNG\r\n\x1a\n"
            and (img.findtext("left"), img.findtext("top"),
                 img.findtext("width"), img.findtext("height"))
            == ("0", "0", "1920", "1080")
            and incs[0].get("content") == "IconButton"
            and params.get("onclick") == "ActivateWindow(settings)"
            and dc is not None and dc.get("always") == "true"
            and dc.text == params.get("control_id")
            and labels == ["$INFO[System.Time]"])


def test_settings_three_tiles():
    """Settings keeps System information, System and CoreELEC, in that order,
    in one panel; the second panel, the caption and the jumps to it go."""
    files = ks.build(_stock())
    root = ET.fromstring(files["xml/Settings.xml"])
    panels = [c for c in root.iter("control") if c.get("type") == "panel"]
    items = panels[0].find("content").findall("item") if panels else []
    labels = [c.findtext("label") for c in root.iter("control")
              if c.get("type") == "label"]
    return (len(panels) == 1 and panels[0].get("id") == "9000"
            and [i.findtext("onclick") for i in items]
            == ["ActivateWindow(systeminfo)", "ActivateWindow(SystemSettings)",
                "RunAddon(service.coreelec.settings)"]
            and items[2].findtext("visible")
            == "System.AddonIsEnabled(service.coreelec.settings)"
            and panels[0].find("onup") is None and panels[0].find("ondown") is None
            and "$LOCALIZE[5]" not in labels
            and root.findtext("defaultcontrol") == "9000")


def test_settings_reshaped_stays_stock():
    """A Settings window without all three tiles is left stock, and the rest
    of the skin still builds."""
    stock = _stock()
    stock["xml/Settings.xml"] = SETTINGS.replace(b"RunAddon(service.coreelec.settings)", b"Noop")
    files = ks.build(stock)
    bad = dict(_stock()); bad["xml/Settings.xml"] = b"<not xml"
    files2 = ks.build(bad)
    return ("xml/Settings.xml" not in files and "xml/Settings.xml" not in files2
            and "xml/DialogSeekBar.xml" in files)


def test_build_needs_every_file():
    stock = _stock()
    del stock["xml/DialogSeekBar.xml"]
    try:
        ks.build(stock)
        return False
    except ks.SkinPatchError:
        return True


def test_build_output():
    files = ks.build(_stock())
    return set(files) == {"addon.xml", "xml/Custom_1109_TopBarOverlay.xml",
                          "xml/DialogSeekBar.xml", "xml/DialogNotification.xml",
                          "xml/DialogSelect.xml", "xml/Variables.xml",
                          "xml/Custom_1190_SymphonyOSD.xml", "xml/Home.xml",
                          "media/symphony_home.png", "xml/Settings.xml"}


TESTS = [
    ("Patch moves every stock control", test_patch_moves_every_control),
    ("Patch keeps window elements and text", test_patch_keeps_window_level_elements_and_text),
    ("Top slides down, seek bar up", test_patch_directions),
    ("Inset 0 is the stock layout", test_patch_has_no_zero_condition),
    ("Unfamiliar window shapes are refused", test_patch_refuses_other_shapes),
    ("addon.xml gets the new id and name", test_addon_renamed),
    ("Only stock Estuary is patched", test_addon_must_be_stock_estuary),
    ("Each window slides the right way", test_directions_per_window),
    ("Hide slides travel the inset too", test_hide_slides_travel_the_inset),
    ("Paused tuck removed, bar stays", test_paused_tuck_removed),
    ("Inward and non-hide slides untouched", test_inward_slides_untouched),
    ("Wrapper vanishes when the window closes", test_wrapper_repeats_window_conditions),
    ("Select dialog shrinks into the picture", test_select_dialog_fits_the_picture),
    ("Info panel removed from the seek bar only", test_info_panel_removed),
    ("File-name title shows the database title", test_file_name_title_replaced),
    ("Format line shows the film's aspect", test_format_line_aspect),
    ("Symphony OSD window", test_osd_window),
    ("Home is the GUI background, clock and settings", test_home_is_background_clock_and_settings),
    ("Settings keeps three tiles in one row", test_settings_three_tiles),
    ("A reshaped Settings window stays stock", test_settings_reshaped_stays_stock),
    ("Live bitrates on the playing format line", test_live_bitrates),
    ("A missing stock file is refused", test_build_needs_every_file),
    ("Build output", test_build_output),
]


def main():
    passed = failed = 0
    for name, fn in TESTS:
        try:
            ok = fn()
        except Exception as e:
            print("✗ %s (%s: %s)" % (name, type(e).__name__, e))
            ok = None
        if ok:
            print("✓ " + name)
            passed += 1
        else:
            if ok is False:
                print("✗ " + name)
            failed += 1
    print("\nPassed: %d, Failed: %d" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
