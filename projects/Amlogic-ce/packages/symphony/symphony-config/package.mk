# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="symphony-config"
PKG_VERSION="1.0"
PKG_LICENSE="GPL-2.0-only"
PKG_SITE="https://github.com/alexscotti/CoreELEC"
PKG_URL=""
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Symphony's own settings for this box, in the image rather than in a /storage snapshot: every one CoreELEC does not already default to."
PKG_TOOLCHAIN="manual"

# Everything about THIS rig that the stock image cannot know. It used to ride
# in a 475-entry tarball of one box's /storage, written onto the stick by
# am9usb at image time and never touched again; the box's own settings and a
# clone of one box were the same artifact, and the only copy of a setting was
# that tarball.
#
# These files go where CoreELEC's own first-boot hooks look, so /storage needs
# no configuration at all and a wiped, factory-reset or freshly written
# /storage comes back correct on the next boot:
#
#   /usr/config/*                  userconfig.service -> /storage/.config/
#                                  (cp -iRp: never overwrites what is there)
#   /usr/cache/*                   usercache.service  -> /storage/.cache/
#   /usr/share/symphony/userdata/  symphony-userdata.service, below
#
# guisettings.xml goes through our own unit rather than CoreELEC's
# /usr/share/kodi/config/, which would be the obvious home for it: the kodi
# package owns that path and installs AFTER this one, so a copy left there is
# silently replaced by Kodi's own 4-line default (measured: the first build of
# this package shipped the stock file). Our unit runs at sysinit, so by the
# time kodi-config asks whether userdata has a guisettings.xml, ours is there
# and it does nothing.
#
# NOT here, because the image already has them byte for byte and the hooks
# above restore them: aacs/KEYDB.cfg, hosts.conf, idmapd.conf, nfs.conf,
# modprobe.d/disable-spdif-for-hd-audio.conf, every *.sample and README,
# .cache/shadow (the root password IS /usr/cache/shadow), the avahi/crond/
# bluez/samba service files (their *-defaults units recreate them), and
# sources.xml / RssFeeds.xml / profiles.xml (kodi-config and Kodi do).
#
# guisettings.xml carries 30 settings. The box's own file has 460, but Kodi
# marks 427 of them default="true" -- its own statement that the value is the
# default and it merely wrote it out -- and re-derives them from
# /usr/share/kodi/system/settings/*.xml in THIS image. Only what differs is
# here. Two of the 30 are this rig's and nothing else's: videoscreen.whitelist
# (mode strings from the display's EDID, including the 1080p frame-packed
# modes 3D switches into) and the audiooutput devices (the AM9 Pro's ALSA
# names). A different display or box needs them re-read.
#
# services.deviceuuid is deliberately absent: Kodi generates one per box
# rather than every box cloning the one the tarball was captured from.
makeinstall_target() {
  mkdir -p ${INSTALL}/usr/config ${INSTALL}/usr/cache \
           ${INSTALL}/usr/share/symphony/userdata \
           ${INSTALL}/usr/lib/systemd/system/sysinit.target.wants \
           ${INSTALL}/usr/lib/systemd/system/tz-data.service.d \
           ${INSTALL}/usr/lib/tmpfiles.d

  cp -a ${PKG_DIR}/config/usr-config/.    ${INSTALL}/usr/config/
  cp -a ${PKG_DIR}/config/usr-cache/.     ${INSTALL}/usr/cache/
  cp -a ${PKG_DIR}/config/userdata/.      ${INSTALL}/usr/share/symphony/userdata/
  chmod +x ${INSTALL}/usr/config/autostart.sh

  cp ${PKG_DIR}/units/symphony-userdata.service ${INSTALL}/usr/lib/systemd/system/
  # sysinit.target, matching its WantedBy and the two hooks it sits beside
  # (userconfig.service, usercache.service): it has to be done before Kodi,
  # and like them it is DefaultDependencies=no.
  ln -sf ../symphony-userdata.service \
    ${INSTALL}/usr/lib/systemd/system/sysinit.target.wants/symphony-userdata.service
  cp ${PKG_DIR}/units/tz-data-after-usercache.conf \
    ${INSTALL}/usr/lib/systemd/system/tz-data.service.d/
  cp ${PKG_DIR}/units/symphony.conf ${INSTALL}/usr/lib/tmpfiles.d/
}
