#!/usr/bin/env bash
# Diagnóstico de SOLO LECTURA: no instala ni modifica nada.
# Uso:  bash deploy/check.sh            (opcional: PUBLIC_PORT=8081 APP_PORT=8765)
PUBLIC_PORT="${PUBLIC_PORT:-8081}"
APP_PORT="${APP_PORT:-8765}"

section() { printf '\n===== %s =====\n' "$1"; }

section "Sistema"
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
python3 --version 2>&1

section "Puertos en uso (proceso que escucha)"
ss -ltnp 2>/dev/null | awk 'NR==1 || /LISTEN/' | sed -E 's/users:\(\("([^"]+)".*/\1/'

section "Servidores web y paneles detectados"
for svc in nginx apache2 httpd caddy lsws openlitespeed docker; do
  systemctl is-active --quiet "$svc" 2>/dev/null && echo "ACTIVO: $svc"
done
command -v nginx >/dev/null && echo "nginx binario: $(command -v nginx) ($(nginx -v 2>&1))"
[ -d /etc/nginx/sites-enabled ] && echo "sites-enabled: $(ls /etc/nginx/sites-enabled | tr '\n' ' ')"
[ -d /etc/nginx/conf.d ] && echo "conf.d: $(ls /etc/nginx/conf.d 2>/dev/null | tr '\n' ' ')"
[ -d /www/server/panel ] && echo "PANEL: aaPanel"
[ -d /home/clp ] || command -v clpctl >/dev/null && echo "PANEL: CloudPanel"
[ -d /data/coolify ] && echo "PANEL: Coolify"
[ -d /usr/local/hestia ] && echo "PANEL: HestiaCP"
[ -d /usr/local/CyberCP ] && echo "PANEL: CyberPanel"
[ -d /opt/easypanel ] || [ -d /etc/easypanel ] && echo "PANEL: Easypanel"
command -v docker >/dev/null && { echo "Contenedores:"; docker ps --format '  {{.Names}}  {{.Ports}}' 2>/dev/null; }

section "Firewall"
command -v ufw >/dev/null && ufw status 2>/dev/null | head -20

section "Puertos para CiclonAI"
for p in "$PUBLIC_PORT" "$APP_PORT"; do
  if ss -ltn "sport = :$p" 2>/dev/null | grep -q LISTEN; then echo "Puerto $p: OCUPADO"; else echo "Puerto $p: libre"; fi
done
[ -e /opt/ciclonai ] && echo "/opt/ciclonai ya existe" || echo "/opt/ciclonai: libre"
