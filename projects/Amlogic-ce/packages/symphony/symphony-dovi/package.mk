# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="symphony-dovi"
PKG_VERSION="1.0"
PKG_LICENSE="GPL-2.0-only"
PKG_SITE="https://github.com/alexscotti/CoreELEC"
PKG_URL=""
PKG_DEPENDS_TARGET="toolchain Python3"
PKG_LONGDESC="Captures Amlogic's Dolby Vision kernel module (dovi.ko) from a FAT32 USB stick at boot, for CoreELEC's dovi-loader."
PKG_TOOLCHAIN="manual"

# CoreELEC ships no dovi.ko: the module is Amlogic's, and every user supplies
# it. scripts/symphony-dovi copies a valid one from the root of any FAT32
# stick to /storage/.config/dovi.ko, where dovi-loader looks, and checks it
# is an aarch64 Dolby Vision kernel module for a new enough kernel first
# (dovi-loader does not check that path). Once captured, later boots do not
# look at sticks at all. The script's docstring has the details.
#
#   symphony-dovi.service          the scan, before opentee_linuxdriver.service
#                                  (which runs dovi-loader)
#   symphony-dovi-notify.service   one toast through Kodi once it is up, when
#                                  the module loaded
makeinstall_target() {
  sh ${PKG_DIR}/test_symphony_dovi.sh

  mkdir -p ${INSTALL}/usr/lib/coreelec ${INSTALL}/usr/lib/systemd/system
  cp ${PKG_DIR}/scripts/symphony-dovi ${INSTALL}/usr/lib/coreelec/
  chmod +x ${INSTALL}/usr/lib/coreelec/symphony-dovi
  cp ${PKG_DIR}/system.d/symphony-dovi.service \
     ${PKG_DIR}/system.d/symphony-dovi-notify.service \
     ${INSTALL}/usr/lib/systemd/system/
}

post_install() {
  enable_service symphony-dovi.service
  enable_service symphony-dovi-notify.service
}
