# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026-present Alex Scotti

PKG_NAME="makemkv-ffmpeg"
PKG_VERSION="7.1.5"
PKG_SHA256="de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f"
PKG_LICENSE="LGPL-2.1-or-later"
PKG_SITE="https://ffmpeg.org"
PKG_URL="https://ffmpeg.org/releases/ffmpeg-${PKG_VERSION}.tar.xz"
PKG_SOURCE_DIR="ffmpeg-${PKG_VERSION}"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="A minimal static FFmpeg (the FLAC encoder only), linked into MakeMKV's libmakemkv and installed nowhere."
# -sysroot: these are FFmpeg 7 headers and libraries; the shared sysroot holds
# the image's FFmpeg 9 (Kodi's), and they must not meet. makemkv finds this
# copy through PKG_DEPENDS_CONFIG instead.
PKG_BUILD_FLAGS="-sysroot"

# Built with SYMPHONY_THEATER=yes only, as a build dependency of makemkv.
#
# makemkv-oss 2.0.0 does not compile against FFmpeg 9: its libffabi reads
# AVCodec fields FFmpeg 9 removed. All libmakemkv wants from FFmpeg is the
# FLAC encoder (lossless audio when remuxing), so it gets this: libavcodec and
# libavutil, static and PIC, FLAC encoder only, no programs, no avformat. It
# is linked INTO libmakemkv.so.1, which then has no FFmpeg runtime dependency
# at all (makemkv checks that) and the image's FFmpeg 9 is untouched.
# --disable-autodetect: without it configure finds libdrm (and the like) in
# the sysroot and libmakemkv.so.1 ends up NEEDing libdrm.so.2 for a FLAC
# encoder.
#
# Nothing of this package reaches the image: makeinstall_target installs only
# headers, .a files and .pc files, all of which the image install leaves out,
# and it fails the build if anything else turns up.

pre_configure_target() {
  # FFmpeg's configure builds in its source tree, as packages/multimedia/ffmpeg.
  cd ${PKG_BUILD}
  rm -rf .${TARGET_NAME}
}

configure_target() {
  ./configure --prefix="/usr" \
              --cpu="${TARGET_CPU}${TARGET_CPU_FLAGS}" \
              --arch="${TARGET_ARCH}" \
              --enable-cross-compile \
              --cross-prefix="${TARGET_PREFIX}" \
              --sysroot="${SYSROOT_PREFIX}" \
              --sysinclude="${SYSROOT_PREFIX}/usr/include" \
              --target-os="linux" \
              --nm="${NM}" \
              --ar="${AR}" \
              --as="${CC}" \
              --cc="${CC}" \
              --ld="${CC}" \
              --host-cc="${HOST_CC}" \
              --host-cflags="${HOST_CFLAGS}" \
              --host-ldflags="${HOST_LDFLAGS}" \
              --extra-cflags="${CFLAGS}" \
              --extra-ldflags="${LDFLAGS}" \
              --pkg-config="${TOOLCHAIN}/bin/pkg-config" \
              --disable-shared \
              --enable-static \
              --enable-pic \
              --disable-programs \
              --disable-doc \
              --disable-avdevice \
              --disable-avformat \
              --disable-swscale \
              --disable-swresample \
              --disable-avfilter \
              --disable-everything \
              --disable-autodetect \
              --enable-encoder=flac
}

makeinstall_target() {
  # install-libs and install-headers (with the .pc files) only: the top-level
  # "install" also runs fftools' install-data, which would put FFmpeg 7's
  # share/ffmpeg files where FFmpeg 9's are.
  make install-libs install-headers DESTDIR=${INSTALL}

  local extra
  extra="$(cd ${INSTALL} && find . -type f ! -name '*.a' ! -name '*.pc' ! -path './usr/include/*')"
  if [ -n "${extra}" ]; then
    die "makemkv-ffmpeg would put files in the image: ${extra}"
  fi
}
