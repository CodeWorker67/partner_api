#!/usr/bin/env bash
# Развёртывание partner_api + шаблона bot_partner на Ubuntu VPS.
#   bash /root/partner_api/scripts/deploy-vps.sh
set -euo pipefail

[[ "${EUID}" -eq 0 ]] || { echo "Запустите от root" >&2; exit 1; }

API_DIR="${API_DIR:-/root/partner_api}"
BOT_TEMPLATE="${BOT_TEMPLATE:-/root/bot_partner}"
DB_DIR="${DB_DIR:-/root/database}"

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip rsync

mkdir -p "${DB_DIR}/backups" "${BOT_TEMPLATE}"

if [[ ! -d "${API_DIR}/venv" ]]; then
  python3 -m venv "${API_DIR}/venv"
fi
"${API_DIR}/venv/bin/pip" install -q -r "${API_DIR}/requirements.txt"

if [[ ! -f "${API_DIR}/.env" ]]; then
  cp "${API_DIR}/.env.example" "${API_DIR}/.env"
  echo "Создан ${API_DIR}/.env — задайте PARTNER_VPS_API_KEY и пути."
fi

if [[ ! -f "${API_DIR}/shared.env" ]]; then
  cat >"${API_DIR}/shared.env" <<'EOF'
PANEL_URL=
PANEL_API_TOKEN=
SHORT_UUID_SECRET=
API_FREEKASSA=
SHOP_ID_FREEKASSA=
FREEKASSA_SERVER_IP=
CRYPTOBOT_API_TOKEN=
SUPPORT_URL=
DOCUMENT_URL_1=
DOCUMENT_URL_2=
REFERRAL_PROCENT=30
PARTNER_SHARE_REF=20
PARTNER_SHARE_DEFAULT=50
PARTNER_MIN_WITHDRAW=3000
DEFAULT_TRIAL_DAYS=3
EOF
  echo "Создан ${API_DIR}/shared.env — заполните общие ключи для ботов-партнёров."
fi

cat >/etc/systemd/system/partner-api.service <<EOF
[Unit]
Description=Partner VPS Orchestrator API
After=network.target

[Service]
Type=simple
WorkingDirectory=${API_DIR}
EnvironmentFile=${API_DIR}/.env
ExecStart=${API_DIR}/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now partner-api.service
echo "✅ partner-api.service запущен. Health: curl http://127.0.0.1:8090/bots/health"
echo "Шаблон бота: ${BOT_TEMPLATE} (скопируйте код partner_bot в эту папку)"
