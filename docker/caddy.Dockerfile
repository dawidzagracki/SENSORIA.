# syntax=docker/dockerfile:1
FROM caddy:2.11.4-alpine
ENV XDG_DATA_HOME=/data \
    XDG_CONFIG_HOME=/config
RUN addgroup -S -g 10001 caddy \
    && adduser -S -D -H -u 10001 -G caddy caddy \
    && mkdir -p /data /config /etc/caddy \
    && chown -R caddy:caddy /data /config /etc/caddy
COPY --chown=caddy:caddy docker/Caddyfile /etc/caddy/Caddyfile
USER 10001:10001
EXPOSE 8080 8443 8443/udp
