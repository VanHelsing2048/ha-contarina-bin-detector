FROM ghcr.io/home-assistant/base:3.21

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
    io.hass.name="Contarina Bin Detector" \
    io.hass.description="Detects which Contarina bin color is visible in an RTSP camera area and publishes a Home Assistant sensor" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache \
    python3 \
    py3-numpy \
    py3-opencv \
    py3-requests \
    tzdata

COPY rootfs /

RUN chmod a+x /etc/services.d/contarina/run /usr/bin/contarina_bin_detector.py
