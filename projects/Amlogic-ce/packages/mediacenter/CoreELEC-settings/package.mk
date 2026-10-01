# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2022-present Team CoreELEC (https://coreelec.org)

PKG_NAME="CoreELEC-settings"
PKG_VERSION="ee00f10e24371f99d31f96feec9b8dafba2da9c9"
PKG_SHA256=""
PKG_LICENSE="GPL"
PKG_SITE="https://coreelec.org"
PKG_URL="https://github.com/CoreELEC/service.coreelec.settings/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET="toolchain Python3 connman dbussy bkeymaps"
PKG_LONGDESC="CoreELEC-settings: is a settings dialog for CoreELEC"

PKG_MAKE_OPTS_TARGET="DISTRONAME=${DISTRONAME} \
                      ADDON_VERSION=${ADDON_VERSION} \
                      ROOT_PASSWORD=${ROOT_PASSWORD}"

post_makeinstall_target() {
  # Symphony: scripts/symphony-hostname names the box
  # symphony-coreelec-<channel> from a SYMPHONY USB stick (0 without one), and
  # patches/ keeps the add-on from resetting it to CoreELEC at Kodi start.
  sh ${PKG_DIR}/test_symphony_hostname.sh

  mkdir -p ${INSTALL}/usr/lib/coreelec
  cp ${PKG_DIR}/scripts/* ${INSTALL}/usr/lib/coreelec

  ADDON_INSTALL_DIR=${INSTALL}/usr/share/kodi/addons/service.coreelec.settings
  python_compile ${ADDON_INSTALL_DIR}/resources/lib/
  python_compile ${ADDON_INSTALL_DIR}/oe.py
}

post_install() {
  enable_service backup-restore.service
  enable_service factory-reset.service
  enable_service symphony-hostname.service
}
