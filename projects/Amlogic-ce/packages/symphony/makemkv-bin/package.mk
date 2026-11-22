# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="makemkv-bin"
PKG_VERSION="2.0.0"
PKG_SHA256="f1265e74875a186efdfbbbec7459a64e969033515e53cbc4d805f0a374f0a124"
PKG_LICENSE="nonfree"
PKG_SITE="https://www.makemkv.com/"
PKG_URL="https://www.makemkv.com/download/makemkv-bin-${PKG_VERSION}.tar.gz"
PKG_LONGDESC="MakeMKV's prebuilt part (makemkvcon and its data files), unpacked for makemkv to install."
PKG_TOOLCHAIN="manual"

# Download and unpack only, like jdk-aarch64-zulu: makemkv lists this in
# PKG_DEPENDS_UNPACK and installs bin/<arch>/makemkvcon and src/share/* from
# its build directory. Built with SYMPHONY_THEATER=yes only.
#
# MakeMKV's license does not allow redistributing this part, so it must never
# be in a public image. Downloading it at build time from a public package.mk
# is fine; shipping what it downloads is not.
