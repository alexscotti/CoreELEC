# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="symphony-config"
PKG_VERSION="2.0"
PKG_LICENSE="GPL-2.0-only"
PKG_SITE="https://github.com/alexscotti/CoreELEC"
PKG_URL=""
PKG_DEPENDS_TARGET="toolchain symphony-defaults"
PKG_LONGDESC="Our theater's own settings for this box, on top of symphony-defaults. Built with SYMPHONY_THEATER=yes only."
PKG_TOOLCHAIN="manual"

# Everything about THIS rig that a public Symphony build must not carry. What
# every Symphony build needs (disc menus, passthrough, the AM9 Pro's audio
# devices, the UR-02 keymap, safemode.disable, the userdata unit and merge) is
# symphony-defaults.
#
# These files go where CoreELEC's own first-boot hooks look, so /storage needs
# no configuration at all and a wiped, factory-reset or freshly written
# /storage comes back correct on the next boot:
#
#   /usr/config/*                  userconfig.service -> /storage/.config/
#                                  (cp -iRp: never overwrites what is there)
#   /usr/cache/*                   usercache.service  -> /storage/.cache/
#   /usr/share/symphony/userdata/  symphony-userdata.service (symphony-defaults)
#   /usr/share/symphony/guisettings.d/50-theater.xml
#                                  symphony-userdata-merge, after
#                                  symphony-defaults' 10-symphony.xml
#
# 50-theater.xml: the skin, no screensaver, the web server (the Symphony
# driver's JSON-RPC) with its password and the EventServer on all interfaces,
# UPnP announce and WS-Discovery off, settinglevel 3, and this rig's display:
# videoscreen.resolution and videoscreen.whitelist (mode strings from the
# display's EDID, including the 1080p frame-packed modes 3D switches into) -
# a different display needs them re-read. Also shutdownstate, addons
# update mode, the DV LED and the playlists path.
#
# Also: the timezone (and tz-data ordered after usercache), the persistent
# journal, SSH via sshd.conf, WoL autostart.sh, cec_HDMI.xml (the box ignores
# TV standby) and oe_settings.xml (CoreELEC's first-run wizard answered,
# AutoUpdate manual, wol on).
#
# NOT here, because the image already has them byte for byte and the hooks
# above restore them: aacs/KEYDB.cfg, hosts.conf, idmapd.conf, nfs.conf,
# modprobe.d/disable-spdif-for-hd-audio.conf, every *.sample and README,
# .cache/shadow (the root password IS /usr/cache/shadow), the avahi/crond/
# bluez/samba service files (their *-defaults units recreate them), and
# sources.xml / RssFeeds.xml / profiles.xml (kodi-config and Kodi do).
makeinstall_target() {
  mkdir -p ${INSTALL}/usr/config ${INSTALL}/usr/cache \
           ${INSTALL}/usr/share/symphony/userdata \
           ${INSTALL}/usr/share/symphony/guisettings.d \
           ${INSTALL}/usr/lib/systemd/system/tz-data.service.d

  cp -a ${PKG_DIR}/config/usr-config/.    ${INSTALL}/usr/config/
  cp -a ${PKG_DIR}/config/usr-cache/.     ${INSTALL}/usr/cache/
  cp -a ${PKG_DIR}/config/userdata/.      ${INSTALL}/usr/share/symphony/userdata/
  cp ${PKG_DIR}/guisettings.d/*.xml       ${INSTALL}/usr/share/symphony/guisettings.d/
  chmod +x ${INSTALL}/usr/config/autostart.sh

  cp ${PKG_DIR}/units/tz-data-after-usercache.conf \
    ${INSTALL}/usr/lib/systemd/system/tz-data.service.d/
}
