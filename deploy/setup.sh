#!/usr/bin/env bash
# Instala o actualiza CiclonAI en un VPS Ubuntu/Debian (Hostinger KVM).
# Uso (como root, desde la carpeta descomprimida del proyecto):
#     bash deploy/setup.sh
# Volver a ejecutarlo actualiza la app con el código nuevo.
set -euo pipefail

APP_DIR=/opt/ciclonai
APP_USER=ciclonai
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta este script como root (o con sudo)."; exit 1; }

echo "==> Instalando paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx fonts-dejavu-core rsync >/dev/null

python3 - <<'EOF' || { echo "Se necesita Python 3.10 o superior (usa Ubuntu 22.04 o 24.04)."; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)
EOF

echo "==> Usuario y archivos de la app en $APP_DIR"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"
rsync -a --delete --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' "$SRC_DIR"/ "$APP_DIR"/

echo "==> Entorno virtual y dependencias"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "==> Servicio systemd"
install -m 644 "$APP_DIR/deploy/ciclonai.service" /etc/systemd/system/ciclonai.service
systemctl daemon-reload
systemctl enable --now ciclonai
systemctl restart ciclonai

echo "==> Nginx"
install -m 644 "$APP_DIR/deploy/nginx-ciclonai.conf" /etc/nginx/sites-available/ciclonai
ln -sf /etc/nginx/sites-available/ciclonai /etc/nginx/sites-enabled/ciclonai
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx >/dev/null
systemctl reload nginx || systemctl restart nginx

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 'Nginx HTTP' >/dev/null
fi

echo "==> Comprobando"
sleep 2
if curl -fsS -o /dev/null http://127.0.0.1/; then
  echo "Listo: CiclonAI está en http://$(hostname -I | awk '{print $1}')/"
else
  echo "La app no responde. Revisa:  journalctl -u ciclonai -n 50 --no-pager"
  exit 1
fi
