#!/bin/bash
# اسکریپت نصب کامل سرور بروودر روی Ubuntu
set -e

echo "═══════════════════════════════════════"
echo "  نصب سرور کنترل گرم‌خانه جوجه اردک"
echo "═══════════════════════════════════════"

# ── ۱. پیش‌نیازها ──────────────────────────────────────
echo "[1/7] نصب پیش‌نیازها..."
sudo apt update -q
sudo apt install -y python3 python3-venv python3-pip postgresql redis-server nginx

# ── ۲. دیتابیس PostgreSQL ──────────────────────────────
echo "[2/7] راه‌اندازی PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo -u postgres psql <<EOF
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'brooder') THEN
    CREATE USER brooder WITH PASSWORD 'brooder_pass_change_me';
  END IF;
END \$\$;
CREATE DATABASE IF NOT EXISTS brooder_db OWNER brooder;
GRANT ALL PRIVILEGES ON DATABASE brooder_db TO brooder;
EOF

# ── ۳. Redis ───────────────────────────────────────────
echo "[3/7] راه‌اندازی Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# ── ۴. پروژه ──────────────────────────────────────────
echo "[4/7] کپی فایل‌های پروژه..."
sudo mkdir -p /opt/brooder_server
sudo cp -r . /opt/brooder_server/
sudo chown -R www-data:www-data /opt/brooder_server

# ── ۵. محیط مجازی Python ──────────────────────────────
echo "[5/7] نصب وابستگی‌های Python..."
sudo -u www-data python3.11 -m venv /opt/brooder_server/venv
sudo -u www-data /opt/brooder_server/venv/bin/pip install -q -r /opt/brooder_server/requirements.txt

# ── ۶. فایل .env ──────────────────────────────────────
echo "[6/7] ایجاد فایل تنظیمات..."
if [ ! -f /opt/brooder_server/.env ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > /opt/brooder_server/.env <<ENVFILE
DATABASE_URL=postgresql+asyncpg://brooder:brooder_pass_change_me@localhost:5432/brooder_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=${SECRET}
API_KEY=${API_KEY}
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=admin1234
SESSION_EXPIRE_HOURS=12
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DEBUG=false
ENVFILE
    echo "⚠️  API_KEY برای ESP: ${API_KEY}"
    echo "⚠️  رمز داشبورد پیش‌فرض: admin1234 — حتماً تغییر دهید!"
fi

# ── ۷. Systemd Service ────────────────────────────────
echo "[7/7] راه‌اندازی سرویس..."
sudo cp /opt/brooder_server/brooder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable brooder
sudo systemctl start brooder

echo ""
echo "✅ نصب کامل شد!"
echo "──────────────────────────────────────"
echo " سرویس: sudo systemctl status brooder"
echo " لاگ:   sudo journalctl -u brooder -f"
echo " API:   http://localhost:8000/docs"
echo "──────────────────────────────────────"
