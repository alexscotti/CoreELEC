# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="symphony-defaults"
PKG_VERSION="1.0"
PKG_LICENSE="GPL-2.0-only"
PKG_SITE="https://github.com/alexscotti/CoreELEC"
PKG_URL=""
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="The settings every Symphony build plays discs with: disc menus, passthrough, the AM9 Pro's audio devices, the UR-02 remote."
PKG_TOOLCHAIN="manual"

# Every Symphony build, public or our theater's. What only our rig needs
# (the skin, the display's mode whitelist, the web server, timezone, ...) is
# symphony-config, built with SYMPHONY_THEATER=yes only.
#
# guisettings.d/10-symphony.xml - settings symphony-userdata-merge gives
# Kodi's guisettings.xml when it lacks them (symphony-userdata.service, at
# sysinit, before Kodi):
#
#   disc.playback=2                 disc menus, the point of the build
#   audiooutput.audiodevice,        the AM9 Pro's ALSA names. They come from
#   audiooutput.passthroughdevice   the dtb this image ships, so they are the
#                                   same on every AM9 Pro that runs it
#   audiooutput.channels=10         7.1; an AVR downmixes for fewer speakers
#   audiooutput.passthrough=true    lossless audio to the AVR
#   audiooutput.streamsilence=0     "Keep audio device alive" off. With it on,
#                                   Kodi streams PCM silence through silent
#                                   menus; after 10 Cloverfield Lane's TrueHD
#                                   trailer the AC-3 main menu opened with
#                                   ~0.5s of loud pulsed static. A playing
#                                   stream keeps the sink open regardless
#   videoplayer.stereoscopic-       1, "Preferred mode": Kodi's default "Ask
#     playbackmode                  me" raises a dialog that wedges a box
#                                   driven over JSON-RPC
#   coreelec.amlogic.dolbyvision.cmv40.append=4
#   filecache.memorysize=128, smb.chunksize=1024
#   myvideos.extract*=false         no thumbnail/flag/HDR10+ extraction passes
#                                   over a library of full discs
#   screensaver.usedimonpause=false, powermanagement.restartplayer=false
#   services.airplay=false          CoreELEC's default is on, with no password
#
# services.deviceuuid is deliberately absent: Kodi generates one per box.
#
# /usr/config (userconfig.service copies it to /storage/.config, never
# overwriting): the UR-02 remote's keymap (rc_maps.cfg + ugoos_ur02.toml;
# without them the remote does nothing), and safemode.disable, which turns
# off Kodi's crash-loop safe mode - it renames /storage/.kodi aside after
# this unit has run, stranding the box on a default profile.
makeinstall_target() {
  # no __pycache__ in PKG_DIR: it would change this package's stamp
  export PYTHONDONTWRITEBYTECODE=1
  python3 ${PKG_DIR}/scripts/test_symphony_userdata_merge.py

  mkdir -p ${INSTALL}/usr/config \
           ${INSTALL}/usr/share/symphony/guisettings.d \
           ${INSTALL}/usr/lib/symphony \
           ${INSTALL}/usr/lib/systemd/system/sysinit.target.wants

  cp -a ${PKG_DIR}/config/usr-config/. ${INSTALL}/usr/config/
  cp ${PKG_DIR}/guisettings.d/*.xml ${INSTALL}/usr/share/symphony/guisettings.d/

  cp ${PKG_DIR}/scripts/symphony-userdata-merge ${INSTALL}/usr/lib/symphony/
  chmod +x ${INSTALL}/usr/lib/symphony/symphony-userdata-merge

  cp ${PKG_DIR}/units/symphony-userdata.service ${INSTALL}/usr/lib/systemd/system/
  # sysinit.target, matching its WantedBy and the two hooks it sits beside
  # (userconfig.service, usercache.service): it has to be done before Kodi,
  # and like them it is DefaultDependencies=no.
  ln -sf ../symphony-userdata.service \
    ${INSTALL}/usr/lib/systemd/system/sysinit.target.wants/symphony-userdata.service
}
