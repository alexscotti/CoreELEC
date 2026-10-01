"""Build Symphony's skin, skin.estuary.symphony, from this image's own Estuary.

Run once at image build time by the kodi-theme-Symphony package:

    python3 symphony_skin.py <stock skin.estuary dir> <output skin dir>

The output directory is already a full copy of stock Estuary; this writes the
patched files over it. The skin ships in the image as a system add-on (listed
in Kodi's addon-manifest.xml, so Kodi enables it on first boot), and the seed's
guisettings.xml selects it, so the box comes up in it from the first frame.

Why it exists: the rig's aspect system zooms a scope film's 16:9 frame so the
PICTURE fills the masked screen, and whatever Kodi draws in the letterbox bars
is off the screen or behind the masking. Estuary draws both of its seek
overlays there -- the time/progress bar at the top of the frame
(Custom_1109_TopBarOverlay.xml) and the seek bar at the bottom
(DialogSeekBar.xml) -- so on chapter skip both were cut off. The same goes
for the notification toast (DialogNotification.xml, 85px down at the top
right) that the SUB and AUD keys raise to name the new track. Estuary has no
setting that moves any of them.

What the patch does: it wraps each window's controls in one group carrying a
conditional slide per possible inset, keyed on the skin string
`symphony_inset` (in 1920x1080 skin pixels). The top overlay slides down by
it, as does the notification; the seek bar slides up. The player.coreelec
driver on Symphony's base sets that string on every play from the film's
aspect (theater mach/base/drivers/kodi_skin.py, inset_for), so a 16:9 film
gets 0 and the stock layout. That module and this one must agree on the skin
string names and the inset grid (INSET_STEP, INSET_MAX): change both together.

Why a patch and not a checked-in skin: generated from the build's own Estuary,
the skin always matches the Kodi it ships with. The edits are made by XML
STRUCTURE (the <controls> element), not a text diff, so Estuary reshuffling
lines does not break it; if the structure itself is gone, the build fails
here rather than shipping a broken skin.

It also replaces the home screen with a plain one -- the Symphony GUI's menu
background, the clock and a settings button (see HOME_FILE) -- and cuts the
Settings screen to three tiles (see SETTINGS_KEEP): on this rig nobody uses
Kodi's menus.
"""

import os
import sys
import xml.etree.ElementTree as ET

STOCK_ID = "skin.estuary"
SKIN_ID = "skin.estuary.symphony"
SKIN_NAME = "Estuary (Symphony)"
INSET_STRING = "symphony_inset"
TITLE_STRING = "symphony_title"
ASPECT_STRING = "symphony_aspect"
OSD_STRING = "symphony_osd"


# Estuary's coordinate space.
SKIN_W = 1920
SKIN_H = 1080

# Insets are generated in steps of INSET_STEP and inset_for rounds UP to one,
# so a quantized overlay only ever lands further inside the picture. INSET_MAX
# is a 4:1 picture, wider than anything filmed.
INSET_STEP = 2
INSET_MAX = 300

# Window file -> what the inset does to it: +1 slides it down, -1 up, FIT
# scales it about the screen centre so the whole frame lands in the picture.
# DialogSelect is every Kodi pick list, including the subtitle and audio
# stream lists the SUB and AUD keys open; at 870px tall it cannot be moved
# into an 800px scope picture, only shrunk into it.
FIT = 0
WINDOWS = {
    "xml/Custom_1109_TopBarOverlay.xml": +1,
    "xml/DialogSeekBar.xml": -1,
    "xml/DialogNotification.xml": +1,
    "xml/DialogSelect.xml": FIT,
}
# Top-level controls removed outright, found by a marker in their subtree.
# DialogSeekBar's info panel (the INFO/GUIDE key) is a poster, the plot and a
# grey band behind them -- and this rig plays discs Kodi has no library entry
# for, so it only ever showed the camera placeholder and "Not available". The
# title, clock, progress bar and format line live elsewhere and stay. A
# marker a new Estuary no longer has removes nothing; the patch still applies.
REMOVE = {
    "xml/DialogSeekBar.xml": ("$VAR[NowPlayingPosterVar]",),
}

# Label controls re-pointed, anywhere in the window, by their exact <label>.
# The info screen's title is Estuary's "now playing" breadcrumbs, which for a
# disc Kodi has no library entry for is the FILE name -- "index.bdmv" for
# every folder play. It shows the film's name from the GUI's database instead,
# which player.coreelec sets per play in the skin string TITLE_STRING (empty
# when the GUI has none, so nothing is shown rather than a file name).
RELABEL = {
    "xml/Custom_1109_TopBarOverlay.xml": {
        "$VAR[NowPlayingBreadcrumbsVar]": "$INFO[Skin.String(%s)]" % TITLE_STRING,
    },
}

ADDON_XML = "addon.xml"

# The info screen's format line ("4K UHD - Dolby Vision - H.265 - 1.78:1") is
# Estuary's MediaVideoPropVar. Its aspect is VideoPlayer.VideoAspect, the
# ENCODED frame's -- 1.78 for every Blu-ray, bars included. While a film plays
# it shows ASPECT_STRING instead: the film's own aspect from the GUI, already
# formatted by aspect_label ("2.40:1", "1.78:1 / 2.40:1"), and nothing at all
# when the GUI does not know it. A new Estuary without that variable keeps
# Kodi's value; the rest of the patch still applies.
#
# Both halves of that line also gain the LIVE bitrate while a film plays --
# what the Oppo's info overlay showed. Kodi 22's Player.Process(videolive/
# audiolivebitrate) labels (measured on the AM9 Pro: 71-84 Mb/s video, ~3.5
# Mb/s audio on a UHD disc, updating each second). Kodi's own debug overlay
# has the same numbers but is drawn at a fixed spot over the top-left of the
# frame -- behind the masking on a scope film -- and cannot be moved.
VARIABLES_XML = "xml/Variables.xml"
MEDIA_PROP_VAR = "MediaVideoPropVar"
LIVE_BITRATE = {
    "MediaVideoPropVar": "$INFO[Player.Process(videolivebitrate), \u2022 ]",
    "MediaAudioPropVar": "$INFO[Player.Process(audiolivebitrate), \u2022 ]",
}
PLAYING = "Window.IsActive(fullscreenvideo)"
KODI_ASPECT = "$INFO[VideoPlayer.VideoAspect, \u2022 ,:1]"
OUR_ASPECT = "$INFO[Skin.String(%s), \u2022 ]" % ASPECT_STRING

# Kodi's Settings screen keeps only these tiles, in this order, in one row
# (matched on each tile's <onclick>, case-insensitively): the rig needs
# System information, System and CoreELEC's own settings, nothing else.
SETTINGS_FILE = "xml/Settings.xml"
SETTINGS_KEEP = ("ActivateWindow(systeminfo)",
                 "ActivateWindow(SystemSettings)",
                 "RunAddon(service.coreelec.settings)")
SETTINGS_CAPTION = "$LOCALIZE[5]"    # the "Settings" label between the rows

STOCK_FILES = (ADDON_XML, VARIABLES_XML, SETTINGS_FILE) + tuple(WINDOWS)


class SkinPatchError(Exception):
    pass


def _parse(data, name):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    try:
        return ET.fromstring(data, parser=parser)
    except ET.ParseError as e:
        raise SkinPatchError("%s: %s" % (name, e))


def _serialize(root):
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def _extend_hide_slides(controls, direction):
    """Make Estuary's own hide slides travel the inset too.

    The top bar slides UP 200px while the info dialog is up (and used to slide
    80px after five seconds paused, now removed by _drop_paused_tuck): in
    stock Estuary that is exactly enough to take it off the top of the
    screen. Inside our inset group it only reaches part way --
    into the masked band, which is what it did on the rig: in place for five
    seconds, then half behind the masking. So every CONDITIONAL slide that
    moves outward (up for a top window, down for a bottom one) gets
    INSET_MAX more travel. It still ends off screen at any inset; at inset 0
    it merely moves further, off screen, in the same 300ms."""
    for anim in controls.iter("animation"):
        if (anim.get("effect") != "slide"
                or (anim.text or "").strip().lower() != "conditional"):
            continue
        try:
            x, y = (int(v) for v in anim.get("end", "").split(","))
        except ValueError:
            continue
        if y * direction < 0:
            anim.set("end", "%d,%d" % (x, y - direction * INSET_MAX))


# Estuary slides the top bar off screen once playback has been paused for five
# seconds (a conditional slide keyed on this timer). On this rig the bar
# STAYS while paused, so that animation is removed outright. Matched on the
# timer name, so if a new Estuary renames it the tuck survives -- and then
# still clears the screen, via _extend_hide_slides.
PAUSED_TUCK_TIMER = "Skin.TimerElapsedSecs(1109_topbaroverlay)"


def _drop_paused_tuck(controls):
    for parent in controls.iter():
        for anim in list(parent.findall("animation")):
            if PAUSED_TUCK_TIMER in (anim.get("condition") or ""):
                parent.remove(anim)


def _remove_marked(controls, markers):
    for child in list(controls):
        text = ET.tostring(child, encoding="unicode")
        if any(m in text for m in markers):
            controls.remove(child)


def _relabel(controls, mapping):
    for ctl in controls.iter("control"):
        if ctl.get("type") != "label":
            continue
        lab = ctl.find("label")
        if lab is not None and (lab.text or "").strip() in mapping:
            lab.text = mapping[lab.text.strip()]


def patch_window(data, direction, name="window"):
    """Wrap every control of a window in one group that slides by the inset.

    Each possible inset gets its own zero-time conditional slide; exactly one
    condition is true at a time, and none while the string is 0 or unset."""
    root = _parse(data, name)
    if root.tag != "window":
        raise SkinPatchError("%s: root is <%s>, not <window>" % (name, root.tag))
    controls = root.find("controls")
    if controls is None or len(controls) == 0:
        raise SkinPatchError("%s: no <controls> to wrap" % name)
    _remove_marked(controls, REMOVE.get(name, ()))
    _relabel(controls, RELABEL.get(name, {}))
    _drop_paused_tuck(controls)
    _extend_hide_slides(controls, direction)
    wrapper = ET.Element("control", {"type": "group"})
    wrapper.text = "\n"
    wrapper.append(ET.Comment(" Symphony: keep inside the masked picture "))
    # The window's own open conditions, repeated on the wrapper. While the
    # window is open they are true, so nothing changes; the moment it starts
    # to CLOSE they are false and everything in it disappears at once, instead
    # of playing out the close. That close is what flashed on the rig: the
    # seek bar's info panel is hidden while seeking or paused, so when the
    # seek ended it turned VISIBLE during the window's 300ms fade-and-slide-out
    # and swept down through the letterbox bar (stock Estuary does the same at
    # the frame's bottom edge). The top bar's slide-out passed through the bar
    # the same way. A window opened by code has no conditions and gains none.
    for cond in root.findall("visible"):
        vis = ET.SubElement(wrapper, "visible")
        vis.text = cond.text
        vis.tail = "\n"
    for v in range(INSET_STEP, INSET_MAX + 1, INSET_STEP):
        cond = "String.IsEqual(Skin.String(%s),%d)" % (INSET_STRING, v)
        if direction == FIT:
            # Only while a film plays: the inset outlives the film, and Kodi's
            # own menus at idle should stay full size.
            attrs = {"effect": "zoom", "start": "100",
                     "end": "%.2f" % (100.0 * (SKIN_H - 2 * v) / SKIN_H),
                     "center": "%d,%d" % (SKIN_W // 2, SKIN_H // 2),
                     "time": "0", "condition": "Player.HasVideo + " + cond}
        else:
            attrs = {"effect": "slide", "start": "0,0",
                     "end": "0,%d" % (direction * v), "time": "0",
                     "condition": cond}
        anim = ET.SubElement(wrapper, "animation", attrs)
        anim.text = "Conditional"
        anim.tail = "\n"
    for child in list(controls):
        controls.remove(child)
        wrapper.append(child)
    controls.append(wrapper)
    return _serialize(root)


def patch_addon_xml(data):
    """Give the copy its own id and name so it installs beside the stock skin."""
    root = _parse(data, ADDON_XML)
    if root.tag != "addon" or root.get("id") != STOCK_ID:
        raise SkinPatchError("addon.xml: not %s (id=%r)" % (STOCK_ID, root.get("id")))
    root.set("id", SKIN_ID)
    root.set("name", SKIN_NAME)
    return _serialize(root)


def patch_variables(data):
    """Point MediaVideoPropVar's aspect at ASPECT_STRING (see VARIABLES_XML)."""
    root = _parse(data, VARIABLES_XML)
    for var in root.iter("variable"):
        name = var.get("name")
        for value in var.findall("value"):
            if not value.text:
                continue
            if name == MEDIA_PROP_VAR and KODI_ASPECT in value.text:
                value.text = value.text.replace(KODI_ASPECT, OUR_ASPECT)
            if name in LIVE_BITRATE and PLAYING in (value.get("condition") or ""):
                value.text += LIVE_BITRATE[name]
    return _serialize(root)


# Symphony's own OSD line -- what the INFO key puts on the projector through
# the HDFury, drawn by Kodi instead while Kodi has the display (no OSD write
# at the fragile Vertex2 at all). A window of our own, not a stock one: a
# dialog that is visible exactly while OSD_STRING is non-empty, so the driver
# shows it by setting the string and clears it by emptying it. One line at
# the top left, 20px down like the HDFury's line, over the same dark gradient
# Estuary's top bar uses; wrapped by patch_window like the stock windows, so
# it rides the inset into the picture on a scope film.
OSD_WINDOW_ID = 1190
OSD_WINDOW_FILE = "xml/Custom_%d_SymphonyOSD.xml" % OSD_WINDOW_ID
OSD_FONT = "font37"


def osd_window_xml():
    return ("""<?xml version="1.0" encoding="UTF-8"?>
<window type="dialog" id="%d">
\t<visible>!String.IsEmpty(Skin.String(%s))</visible>
\t<depth>DepthOSD</depth>
\t<zorder>2</zorder>
\t<controls>
\t\t<control type="image">
\t\t\t<left>0</left>
\t\t\t<top>0</top>
\t\t\t<width>100%%</width>
\t\t\t<height>120</height>
\t\t\t<texture>frame/osdfade.png</texture>
\t\t</control>
\t\t<control type="label">
\t\t\t<left>20</left>
\t\t\t<top>20</top>
\t\t\t<right>20</right>
\t\t\t<height>60</height>
\t\t\t<font>%s</font>
\t\t\t<shadowcolor>text_shadow</shadowcolor>
\t\t\t<label>$INFO[Skin.String(%s)]</label>
\t\t</control>
\t</controls>
</window>
""" % (OSD_WINDOW_ID, OSD_STRING, OSD_FONT, OSD_STRING)).encode()


# The home screen. Nobody drives Kodi from its own menus on this rig -- the
# Symphony GUI picks the film and the driver plays it -- so Estuary's home
# (side menu, add-on/picture/video categories, logo, fanart) is replaced by a
# plain one: the Symphony GUI's menu-screen background full screen, Estuary's
# clock where Estuary puts it (top right), and Estuary's settings button (top
# left), the only control, so it always has focus and OK opens Settings.
# Written whole rather than patched from stock, so a new Estuary's Home.xml
# cannot make it fail; the button and clock use Estuary's own IconButton
# include and font_clock, so they look like stock.
#
# The background ships inside the skin (HOME_BG_FILE). symphony_home.png,
# beside this module, is the
# GUI's menu background (oppogui srcnew menu_screen._make_dark_notes_bg) at
# 1920x1080: select_screen's (30,31,36)->(9,9,11) vertical gradient plus half
# the luminance of resources/notes_dark.png, +/-2 LSB dither. Regenerate it
# the same way if the GUI's background changes.
HOME_FILE = "xml/Home.xml"
HOME_BG_FILE = "media/symphony_home.png"
HOME_BG_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "symphony_home.png")
HOME_IMAGE = "special://skin/" + HOME_BG_FILE
HOME_SETTINGS_ID = 802          # stock Estuary's id for this button


def home_background():
    """The home background PNG's bytes (HOME_BG_SRC)."""
    try:
        with open(HOME_BG_SRC, "rb") as f:
            return f.read()
    except OSError as e:
        raise SkinPatchError("home background: %s" % e)


def home_window_xml():
    return ("""<?xml version="1.0" encoding="UTF-8"?>
<window>
\t<!-- Symphony: the splash, the clock and a settings button -->
\t<defaultcontrol always="true">%(id)d</defaultcontrol>
\t<backgroundcolor>FF000000</backgroundcolor>
\t<controls>
\t\t<control type="image">
\t\t\t<left>0</left>
\t\t\t<top>0</top>
\t\t\t<width>%(w)d</width>
\t\t\t<height>%(h)d</height>
\t\t\t<aspectratio>scale</aspectratio>
\t\t\t<texture>%(image)s</texture>
\t\t</control>
\t\t<control type="group">
\t\t\t<left>30</left>
\t\t\t<top>20</top>
\t\t\t<include content="IconButton">
\t\t\t\t<param name="control_id" value="%(id)d" />
\t\t\t\t<param name="onclick" value="ActivateWindow(settings)" />
\t\t\t\t<param name="icon" value="icons/settings.png" />
\t\t\t\t<param name="label" value="$LOCALIZE[21417]" />
\t\t\t</include>
\t\t</control>
\t\t<control type="grouplist">
\t\t\t<top>0</top>
\t\t\t<right>20</right>
\t\t\t<width>900</width>
\t\t\t<height>200</height>
\t\t\t<align>right</align>
\t\t\t<orientation>horizontal</orientation>
\t\t\t<control type="label">
\t\t\t\t<font>font_clock</font>
\t\t\t\t<shadowcolor>text_shadow</shadowcolor>
\t\t\t\t<height>200</height>
\t\t\t\t<width>auto</width>
\t\t\t\t<label>$INFO[System.Time]</label>
\t\t\t</control>
\t\t</control>
\t</controls>
</window>
""" % {"id": HOME_SETTINGS_ID, "w": SKIN_W, "h": SKIN_H,
       "image": HOME_IMAGE}).encode()


def patch_settings(data):
    """Settings.xml with only the SETTINGS_KEEP tiles, in one row; None when
    the stock window does not have them all (a new Estuary reshaped it), in
    which case the stock file is left alone -- a cosmetic patch must never
    cost the rest of the skin."""
    try:
        root = _parse(data, SETTINGS_FILE)
    except SkinPatchError:
        return None
    keep = [k.lower() for k in SETTINGS_KEEP]
    panels = [c for c in root.iter("control")
              if c.get("type") == "panel" and c.find("content") is not None]
    found = {}
    for panel in panels:
        for item in panel.find("content").findall("item"):
            click = (item.findtext("onclick") or "").strip().lower()
            if click in keep and click not in found:
                found[click] = item
    if not panels or len(found) != len(keep):
        return None
    first = panels[0]
    content = first.find("content")
    for item in list(content):
        content.remove(item)
    for k in keep:
        content.append(found[k])
    for tag in ("onup", "ondown"):
        for el in first.findall(tag):
            first.remove(el)
    parents = {c: p for p in root.iter() for c in p}
    for panel in panels[1:]:
        parents[panel].remove(panel)
    for ctl in list(root.iter("control")):
        if (ctl.get("type") == "label"
                and (ctl.findtext("label") or "").strip() == SETTINGS_CAPTION):
            parents[ctl].remove(ctl)
    return _serialize(root)


def build(stock):
    """Patch the stock files. `stock` maps each STOCK_FILES path to its bytes.
    Returns the files to write over the copy of stock Estuary, by path."""
    missing = [p for p in STOCK_FILES if p not in stock]
    if missing:
        raise SkinPatchError("stock skin is missing " + ", ".join(missing))
    files = {ADDON_XML: patch_addon_xml(stock[ADDON_XML]),
             VARIABLES_XML: patch_variables(stock[VARIABLES_XML])}
    for path, direction in WINDOWS.items():
        files[path] = patch_window(stock[path], direction, path)
    files[OSD_WINDOW_FILE] = patch_window(osd_window_xml(), +1, OSD_WINDOW_FILE)
    files[HOME_FILE] = home_window_xml()
    files[HOME_BG_FILE] = home_background()
    settings = patch_settings(stock[SETTINGS_FILE])
    if settings is not None:
        files[SETTINGS_FILE] = settings
    return files


def main(argv):
    if len(argv) != 3:
        print("usage: symphony_skin.py <stock skin.estuary dir> <output skin dir>",
              file=sys.stderr)
        return 2
    stock_dir, out_dir = argv[1], argv[2]
    stock = {}
    for path in STOCK_FILES:
        with open(os.path.join(stock_dir, path), "rb") as f:
            stock[path] = f.read()
    files = build(stock)
    for path, data in sorted(files.items()):
        dest = os.path.join(out_dir, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        print("symphony_skin: wrote %s (%d bytes)" % (path, len(data)))
    if SETTINGS_FILE not in files:
        print("symphony_skin: WARNING: Settings.xml no longer has the expected "
              "tiles; left stock")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
