# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2025-present Team LibreELEC (https://libreelec.tv)

PKG_NAME="pybind11"
PKG_VERSION="3.1.0"
PKG_SHA256="ef712655692a2e9bf7bb7874c022564a45f91d847ddee987e720cd9e28849665"
PKG_LICENSE="BSD-3-Clause"
PKG_SITE="https://github.com/pybind/pybind11"
PKG_URL="https://github.com/pybind/pybind11/archive/refs/tags/v${PKG_VERSION}.tar.gz"
PKG_DEPENDS_HOST="scikit-build-core:host cmake:host"
PKG_LONGDESC="Seamless operability between C++11 and Python"
PKG_TOOLCHAIN="python"

pre_configure_host() {
  cd ..
  rm -rf .${HOST_NAME}
}

pre_make_host() {
  # scikit-build-core locates cmake by searching PATH, and raises
  # CMakeNotFoundError if it is not on it - which is what killed this package
  # at 82/375 on a cold parallel build even with cmake:host declared and
  # already built (verified: the same search succeeds with ${TOOLCHAIN}/bin on
  # PATH and fails with exactly that error without it). cmake:host installs to
  # ${TOOLCHAIN}/bin and is a declared dependency, so name it outright rather
  # than depend on what PATH happens to hold.
  export CMAKE_EXECUTABLE="${TOOLCHAIN}/bin/cmake"
}
