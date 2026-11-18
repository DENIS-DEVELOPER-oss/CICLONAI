#!/usr/bin/env bash
# Instala o actualiza CiclonAI en un VPS Ubuntu/Debian que YA aloja otras webs.
#
#   bash deploy/setup.sh                                  → http://IP:8081
#   PUBLIC_PORT=9090 APP_PORT=8766 bash deploy/setup.sh   → otros puertos
#
# Garantías: no borra ni edita configuraciones de otras webs; solo crea
#   /opt/ciclonai, el servicio "ciclonai" y /etc/nginx/(sites-available|conf.d)/ciclonai*.
# Si algún puerto está ocupado por otra cosa, o la prueba de Nginx falla, se detiene
# y revierte su propio cambio. Volver a ejecutarlo actualiza la app.
set -euo pipefail

PUBLIC_PORT="${PUBLIC_PORT:-8081}"   # puerto por el que se entra desde el navegador
APP_PORT="${APP_PORT:-8765}"         # puerto interno de Gunicorn (solo 127.0.0.1)
APP_DIR=/opt/ciclonai
APP_USER=ciclonai
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "Ejecuta este script como root (o con sudo)."

# ---------------------------------------------------------------- comprobaciones previas
port_owner() { ss -ltnp "sport = :$1" 2>/dev/null | awk '/LISTEN/' | grep -o 'users:(("[^"]*"' | head -1 | cut -d'"' -f2 || true; }

if [ -e "$APP_DIR" ] && [ ! -f "$APP_DIR/deploy/setup.sh" ]; then
  die "$APP_DIR existe y no es de CiclonAI. No lo toco."
fi

owner="$(port_owner "$APP_PORT")"
if [ -n "$owner" ] && ! systemctl is-active --quiet ciclonai; then
  die "El puerto interno $APP_PORT lo usa '$owner'. Elige otro: APP_PORT=8766 bash deploy/setup.sh"
fi
owner="$(port_owner "$PUBLIC_PORT")"
if [ -n "$owner" ] && ! grep -qs "listen $PUBLIC_PORT" /etc/nginx/sites-available/ciclonai /etc/nginx/conf.d/ciclonai.conf; then
  die "El puerto $PUBLIC_PORT lo usa '$owner'. Elige otro: PUBLIC_PORT=9090 bash deploy/setup.sh"
fi

if [ -d /www/server/panel ]; then
  die "Detecté aaPanel: usa su propio Nginx. No instalo nada para no interferir; avísame y lo adaptamos."
fi

# ---------------------------------------------------------------- paquetes
echo "==> Paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip fonts-dejavu-core rsync curl >/dev/null
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
  || die "Se necesita Python 3.10 o superior (Ubuntu 22.04 o 24.04)."

NGINX_FRESH=0
if ! command -v nginx >/dev/null; then
  echo "==> Instalando Nginx (no estaba instalado; no arrancará en el puerto 80)"
  # Evita que Nginx arranque solo al instalarse e intente ocupar el puerto 80 de otras webs.
  printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d
  apt-get install -y -qq nginx >/dev/null || { rm -f /usr/sbin/policy-rc.d; die "No se pudo instalar Nginx."; }
  rm -f /usr/sbin/policy-rc.d
  rm -f /etc/nginx/sites-enabled/default   # sitio de ejemplo recién instalado por nosotros
  NGINX_FRESH=1
fi

# ---------------------------------------------------------------- app
echo "==> Copiando la app a $APP_DIR"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"
rsync -a --delete --exclude '.git' --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
  "$SRC_DIR"/ "$APP_DIR"/

echo "==> Entorno virtual y dependencias"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "==> Servicio systemd 'ciclonai' (Gunicorn en 127.0.0.1:$APP_PORT)"
sed "s/__APP_PORT__/$APP_PORT/g" "$APP_DIR/deploy/ciclonai.service" > /etc/systemd/system/ciclonai.service
systemctl daemon-reload
systemctl enable ciclonai >/dev/null 2>&1
systemctl restart ciclonai

# ---------------------------------------------------------------- nginx (solo nuestro archivo)
echo "==> Nginx en el puerto $PUBLIC_PORT"
if [ -d /etc/nginx/sites-enabled ] && grep -qs 'sites-enabled' /etc/nginx/nginx.conf; then
  CONF=/etc/nginx/sites-available/ciclonai; LINK=/etc/nginx/sites-enabled/ciclonai
else
  CONF=/etc/nginx/conf.d/ciclonai.conf; LINK=""
fi
BACKUP=""
[ -f "$CONF" ] && { BACKUP="$(mktemp)"; cp "$CONF" "$BACKUP"; }
sed -e "s/__PUBLIC_PORT__/$PUBLIC_PORT/g" -e "s/__APP_PORT__/$APP_PORT/g" \
  "$APP_DIR/deploy/nginx-ciclonai.conf" > "$CONF"
[ -n "$LINK" ] && ln -sf "$CONF" "$LINK"

if ! nginx -t 2>/tmp/ciclonai-nginx-test.log; then
  echo "La prueba de Nginx falló; revierto SOLO el archivo de CiclonAI:" >&2
  cat /tmp/ciclonai-nginx-test.log >&2
  if [ -n "$BACKUP" ]; then cp "$BACKUP" "$CONF"; else rm -f "$CONF" ${LINK:+"$LINK"}; fi
  die "Tus otras webs no se modificaron."
fi
if [ "$NGINX_FRESH" = 1 ] || ! systemctl is-active --quiet nginx; then
  systemctl enable nginx >/dev/null 2>&1; systemctl start nginx
else
  systemctl reload nginx     # recarga sin cortar las otras webs
fi

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow "$PUBLIC_PORT"/tcp >/dev/null && echo "==> UFW: puerto $PUBLIC_PORT abierto"
fi

# ---------------------------------------------------------------- verificación
echo "==> Comprobando"
for _ in 1 2 3 4 5; do curl -fsS -o /dev/null "http://127.0.0.1:$PUBLIC_PORT/" && break; sleep 2; done
if curl -fsS -o /dev/null "http://127.0.0.1:$PUBLIC_PORT/"; then
  echo "Listo: CiclonAI está en http://$(hostname -I | awk '{print $1}'):$PUBLIC_PORT/"
  echo "Si no abre desde tu PC, abre el puerto $PUBLIC_PORT/TCP en hPanel → VPS → Firewall."
else
  die "La app no responde. Revisa: journalctl -u ciclonai -n 50 --no-pager"
fi
