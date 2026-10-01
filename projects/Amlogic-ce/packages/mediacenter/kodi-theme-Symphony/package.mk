# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="kodi-theme-Symphony"
PKG_VERSION="1.0"
PKG_LICENSE="GPL-2.0-only AND CC-BY-SA-4.0"
PKG_SITE="https://github.com/alexscotti/CoreELEC-real"
PKG_URL=""
PKG_DEPENDS_TARGET="kodi"
PKG_DEPENDS_UNPACK="kodi"
PKG_LONGDESC="Symphony's skin, skin.estuary.symphony: this image's own Estuary with the seek overlays kept inside a masked picture, a plain home screen and a three-tile Settings screen."
PKG_TOOLCHAIN="manual"

# Built from the Estuary this same build installs (kodi-theme-Estuary takes it
# from the same place), so the skin always matches the Kodi it ships with.
# symphony_skin.py has the why of every change. It ships as a system add-on:
# kodi/package.mk lists it in addon-manifest.xml, which is what makes Kodi
# enable it on first boot (an add-on Kodi merely finds is recorded disabled),
# and the seed's guisettings.xml selects it.
makeinstall_target() {
  local stock="$(get_install_dir kodi)/.noinstall/skin.estuary"
  local skin="${INSTALL}/usr/share/kodi/addons/skin.estuary.symphony"

  # no __pycache__ in PKG_DIR: it would change this package's stamp
  export PYTHONDONTWRITEBYTECODE=1
  python3 ${PKG_DIR}/test_symphony_skin.py

  mkdir -p ${INSTALL}/usr/share/kodi/addons
    cp -a "${stock}" "${skin}"
  python3 ${PKG_DIR}/symphony_skin.py "${stock}" "${skin}"
}
