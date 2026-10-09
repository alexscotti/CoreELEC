# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="symphony-jre"
PKG_VERSION="1.0"
PKG_LICENSE="GPL-2.0-only WITH Classpath-exception-2.0"
PKG_SITE="https://github.com/alexscotti/CoreELEC"
PKG_URL=""
# LOAD-BEARING, do not trim: for a package in the image's dependency closure
# (this one arrives via ADDITIONAL_PACKAGES -> misc-packages) the build installs
# every target dependency into the image, which is what puts the X client
# libraries in /usr/lib. Nothing else does - this is a DISPLAYSERVER="" build
# and the stock image has no libX11 at all. Drop a name here and BD-J loses a
# library with no other source.
PKG_DEPENDS_TARGET="toolchain libXext libXi libXrender chrome-libXtst jre-libXinerama"
PKG_DEPENDS_UNPACK="jdk-${TARGET_ARCH}-zulu"
# PKG_DEPENDS_UNPACK does NOT feed calculate_stamp (see libbluray/package.mk
# for the long version): without this, bumping the Zulu JDK leaves this
# package's deephash unchanged, the build is skipped, and the PREVIOUS JRE is
# reinstalled with nobody told.
PKG_NEED_UNPACK="$(get_pkg_directory jdk-${TARGET_ARCH}-zulu)"
PKG_LONGDESC="The Zulu JRE that runs BD-J disc menus, in the image instead of in a /storage snapshot."
PKG_TOOLCHAIN="manual"

# BD-J menus need a JVM, and CoreELEC ships one only as an add-on you install
# from its repo (packages/addons/tools/jre.zulu). That add-on used to reach the
# box inside the /storage tarball, which made it a pinned 104MB binary in the
# theater repo and, worse, a DIFFERENT build of libbluray's Java half from the
# libbluray.so in SYSTEM - the two drifted silently and a patched jar that is
# never loaded looks exactly like a patch that does not work.
#
# Nothing here is downloaded that the image does not already download:
# jdk-${TARGET_ARCH}-zulu's package.mk has the pinned cdn.azul.com URL and its
# PKG_SHA256, libbluray already lists it in PKG_DEPENDS_UNPACK to build the
# BD-J jars, and that package's post_unpack is what renames jre/lib/aarch64 to
# jre/lib/arm (which libbluray requires) and leaves the symlink back.
#
# The layout is the add-on's, minus its private lib/ directory.
#
# Upstream's add-on carries its own copies of libX11, libxcb, libXext, libXi,
# libXrender, libXtst and libXinerama because an ADD-ON cannot assume anything
# about the image, and on a DISPLAYSERVER="" build it is right not to: the
# stock image has no libX11 anywhere. In the image that reason is gone -
# PKG_DEPENDS_TARGET above puts them in /usr/lib - and a private copy would
# never be used anyway: 98-busybox.conf sets LD_LIBRARY_PATH=/usr/lib and
# 99-kodi.conf APPENDS the addon lib dirs, so /usr/lib is searched first. The
# copies this package used to make were byte-identical to the ones in
# /usr/lib and unreachable behind them.
#
# For the record, since it decides nothing but explains the small dependency
# list: jre/lib/arm/libawt_xawt.so needs libXcomposite and libXrandr too, and
# NEITHER is in the image or in upstream's add-on, so the X AWT backend has
# never been loadable on this box in either scheme. BD-J does not need it -
# libbluray runs its own toolkit (-Dawt.toolkit=java.awt.BDToolkit,
# java.awt.graphicsenv=java.awt.BDGraphicsEnvironment) - and of the seven,
# only libsplashscreen.so (libX11, libXext) has a user at all. The set is
# upstream's; it is kept as-is rather than guessed at.
#
# What the add-on's own profile.d would have done, JAVA_HOME, is done by our
# /etc/profile.d file instead: 00-addons.conf sources profile.d/*.profile out
# of /storage/.kodi/addons/*/ only, never the image side.
#
# LIBBLURAY_CP is deliberately NOT set. The add-on's jre.profile pointed it at
# the add-on's own jars; since libbluray-08-bdj-prefer-installed-jar-over-
# LIBBLURAY_CP (SamuriHL, 2026-09-23) libbluray searches /usr/share/java
# first, which is where this build's own jars are installed, so the jars beside
# the JRE are not read at all and are not copied in below.
makeinstall_target() {
  local dst="${INSTALL}/usr/lib/kodi/addons/tools.jre.zulu"
  mkdir -p ${dst} ${INSTALL}/etc/profile.d

  cp -a $(get_build_dir jdk-${TARGET_ARCH}-zulu)/jre ${dst}

  cat > ${INSTALL}/etc/profile.d/15-symphony-jre.conf <<'PROFILE'
# BD-J menus: libbluray starts a JVM from JAVA_HOME (bdj.c; with none set it
# searches /usr/lib/jvm and friends, where this image has nothing). The JRE
# ships in the image at this path, not as an installed add-on under /storage,
# so set it here -- /etc/profile.d/00-addons.conf only sources
# profile.d/*.profile out of /storage/.kodi/addons/*/.
#
# LIBBLURAY_CP is NOT set on purpose: libbluray prefers the jar installed
# beside it in /usr/share/java, which is this build's own.
export JAVA_HOME="/usr/lib/kodi/addons/tools.jre.zulu"
PROFILE
}
