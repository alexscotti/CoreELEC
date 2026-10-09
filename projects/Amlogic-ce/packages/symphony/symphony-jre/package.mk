# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="symphony-jre"
PKG_VERSION="1.0"
PKG_LICENSE="GPL-2.0-only WITH Classpath-exception-2.0"
PKG_SITE="https://github.com/alexscotti/CoreELEC"
PKG_URL=""
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
# The layout is the add-on's, verbatim, at the ONE path Kodi's own
# /etc/profile.d/00-addons.conf sibling already handles: 99-kodi.conf globs
# /usr/lib/kodi/addons/*/lib into LD_LIBRARY_PATH, which is how the JRE finds
# the X libraries it carries (none of libX11/Xext/Xi/Xrender/Xtst/Xinerama/xcb
# is in SYSTEM). What that glob does NOT do is source profile.d/*.profile from
# the image side - 00-addons.conf reads /storage/.kodi/addons/*/ only - so
# JAVA_HOME is set by our own /etc/profile.d file instead of the add-on's
# jre.profile.
#
# LIBBLURAY_CP is deliberately NOT set. The add-on's jre.profile pointed it at
# the add-on's own jars; since libbluray-08-bdj-prefer-installed-jar-over-
# LIBBLURAY_CP (SamuriHL, 2026-09-23) libbluray searches /usr/share/java
# first, which is where this build's own jars are installed, so the jars beside
# the JRE are not read at all and are not copied in below.
_pkg_copy_lib() {
  find "${2}/usr/lib" -regextype sed -regex ".*/${1}\.so\.[0-9]*" \
    -exec cp {} "${INSTALL}/usr/lib/kodi/addons/tools.jre.zulu/lib" \;
}

makeinstall_target() {
  local dst="${INSTALL}/usr/lib/kodi/addons/tools.jre.zulu"
  mkdir -p ${dst}/lib ${INSTALL}/etc/profile.d

  cp -a $(get_build_dir jdk-${TARGET_ARCH}-zulu)/jre ${dst}

  # The libraries the JVM needs that SYSTEM does not have. Same list as the
  # add-on's, and the same reason: this is a no-X11 image (DISPLAYSERVER is
  # empty), so all of them have to come along, not just the two.
  _pkg_copy_lib libXtst     $(get_install_dir chrome-libXtst)
  _pkg_copy_lib libXinerama $(get_install_dir jre-libXinerama)
  if [ "${DISPLAYSERVER}" != "X11" ]; then
    _pkg_copy_lib libXi      $(get_install_dir libXi)
    _pkg_copy_lib libXrender $(get_install_dir libXrender)
    _pkg_copy_lib libX11     $(get_install_dir libX11)
    _pkg_copy_lib libXext    $(get_install_dir libXext)
    _pkg_copy_lib libxcb     $(get_install_dir libxcb)
  fi

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
