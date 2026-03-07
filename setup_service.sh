#!/bin/bash
set -e

echo '📝 Creating systemd unit file...'

sudo tee /etc/systemd/system/phangan-api.service > /dev/null << 'EOF'
[Unit]
Description=Phangan Events API (FastAPI + Uvicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=elcrypto
Group=elcrypto
WorkingDirectory=/home/elcrypto/phangan_api
Environment=PATH=/home/elcrypto/phangan_api/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/elcrypto/phangan_api/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 62537 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=phangan-api

NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/elcrypto/phangan_api /home/elcrypto/TG_parcer/media /tmp
ProtectHome=false
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo '🔄 Reloading systemd...'
sudo systemctl daemon-reload

echo '✅ Enabling auto-start...'
sudo systemctl enable phangan-api

echo '🚀 Starting service...'
sudo systemctl restart phangan-api

sleep 2
echo ''
sudo systemctl status phangan-api --no-pager
echo ''
echo '✅ Done! Commands:'
echo '  sudo systemctl status phangan-api'
echo '  sudo journalctl -u phangan-api -f'
echo '  sudo systemctl restart phangan-api'
