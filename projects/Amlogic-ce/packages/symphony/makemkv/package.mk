# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="makemkv"
PKG_VERSION="2.0.0"
PKG_SHA256="435316b2d219eb48c880526557addd076b5f5e6de5171424c7651f9cac95b161"
# The open-source half is under MakeMKV's own license (LGPL libraries plus
# the "MakeMKV GUI" license); makemkvcon, installed below, is not free.
PKG_LICENSE="nonfree"
PKG_SITE="https://www.makemkv.com/"
PKG_URL="https://www.makemkv.com/download/makemkv-oss-${PKG_VERSION}.tar.gz"
PKG_SOURCE_DIR="makemkv-oss-${PKG_VERSION}"
PKG_DEPENDS_TARGET="toolchain openssl zlib expat makemkv-ffmpeg"
PKG_DEPENDS_CONFIG="makemkv-ffmpeg"
PKG_DEPENDS_UNPACK="makemkv-bin"
# calculate_stamp hashes only this package's own directory and
# PKG_NEED_UNPACK, never its dependencies (see symphony-jre): without these,
# bumping makemkv-bin would reinstall the previous makemkvcon, and changing
# makemkv-ffmpeg would leave libmakemkv linked against the previous build.
PKG_NEED_UNPACK="$(get_pkg_directory makemkv-bin) $(get_pkg_directory makemkv-ffmpeg)"
PKG_LONGDESC="MakeMKV's libmmbd, which libbluray falls back to for AACS / AACS2 discs libaacs cannot open, and makemkvcon behind it."
PKG_TOOLCHAIN="configure"
# -sysroot: nothing builds against these. -strip: makemkvcon is a prebuilt
# binary and is installed exactly as shipped (the oss libraries are stripped
# by their own Makefile).
PKG_BUILD_FLAGS="-sysroot -strip"
PKG_CONFIGURE_OPTS_TARGET="--disable-gui --disable-qt5"

# Built with SYMPHONY_THEATER=yes only (projects/Amlogic-ce/devices/
# Amlogic-no/options): MakeMKV's license forbids redistributing makemkvcon,
# so a public image must never carry this. Downloading it here is fine.
#
# Why: the theater's USB drive is a LibreDrive drive and its UHD discs use
# AACS2 bus encryption, which libaacs cannot do (and the host certificate it
# would need is revoked). libbluray (src/libbluray/disc/aacs.c, _open_libaacs)
# tries "libaacs" first and then "libmmbd", so with libmmbd.so.0 in /usr/lib
# the same Kodi plays those discs; nothing is configured. libmmbd does the
# work by spawning makemkvcon, which it finds through $MAKEMKVCON or a fixed
# list (/bin, /usr/bin, /usr/local/bin: makemkvgui/src/api_linux.cpp) - never
# PATH - so it goes in /usr/bin, and its data files where its own Makefile
# installs them, /usr/share/MakeMKV.
#
# FFmpeg: libmakemkv does not compile against the image's FFmpeg 9, so it is
# built against makemkv-ffmpeg (a static FFmpeg 7.1.5, FLAC encoder only),
# found through PKG_DEPENDS_CONFIG. The headers on its pkg-config -I path come
# before the sysroot's, and its -L directory (static libraries only) before
# the sysroot's libavcodec.so, so FFmpeg 9 is not touched.
# post_makeinstall_target fails the build if libmakemkv.so.1 needs anything
# beyond what the hand-built copy verified on the box did: a shared FFmpeg,
# or a library the static one picked up (libdrm and libX11 did, before
# makemkv-ffmpeg had --disable-autodetect).
#
# Installed (matching both upstream Makefiles' install targets):
#   /usr/lib/libmmbd.so.0 libmakemkv.so.1 libdriveio.so.0
#   /usr/bin/mmccextr mmgplsrv                (oss)
#   /usr/bin/makemkvcon, sdftool -> makemkvcon (bin)
#   /usr/share/MakeMKV/appdata.tar blues.jar blues.policy (bin)
#
# makemkv-bin's own Makefile makes "install" wait for the EULA to be accepted
# interactively (src/ask_eula.sh); that step is not run here.

pre_configure_target() {
  # The Makefile names its sources relative to the top of the tree, so it
  # builds in place.
  cd ${PKG_BUILD}
  rm -rf .${TARGET_NAME}
}

post_makeinstall_target() {
  local dyn needs
  dyn="$(${TARGET_PREFIX}readelf -d ${INSTALL}/usr/lib/libmakemkv.so.1)" || die "makemkv: cannot read libmakemkv.so.1"
  echo "${dyn}" | grep -q '(NEEDED)' || die "makemkv: no NEEDED entries in libmakemkv.so.1?"
  needs="$(echo "${dyn}" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' |
           grep -vxE 'libstdc\+\+\.so\.6|libcrypto\.so\.3|libz\.so\.1|libexpat\.so\.1|libm\.so\.6|libc\.so\.6|libgcc_s\.so\.1' || :)"
  if [ -n "${needs}" ]; then
    die "libmakemkv.so.1 needs more than it should (makemkv-ffmpeg is linked in, and needs nothing): ${needs}"
  fi

  local bin_arch
  case "${TARGET_ARCH}" in
    aarch64) bin_arch=arm64 ;;
    arm)     bin_arch=armhf ;;
    x86_64)  bin_arch=amd64 ;;
    *)       die "makemkv: no makemkvcon for ${TARGET_ARCH}" ;;
  esac

  local bin="$(get_build_dir makemkv-bin)"
  mkdir -p ${INSTALL}/usr/bin ${INSTALL}/usr/share/MakeMKV
  install -m 0755 ${bin}/bin/${bin_arch}/makemkvcon ${INSTALL}/usr/bin/makemkvcon
  ln -sf makemkvcon ${INSTALL}/usr/bin/sdftool
  install -m 0644 ${bin}/src/share/appdata.tar \
                  ${bin}/src/share/blues.jar \
                  ${bin}/src/share/blues.policy \
                  ${INSTALL}/usr/share/MakeMKV/
}
