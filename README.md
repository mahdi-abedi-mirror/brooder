# مستندات کامل — سیستم کنترل گرم‌خانه جوجه اردک
نسخه ۱.۰.۰

---

## فهرست مطالب
1. معماری سیستم
2. پیش‌نیازها
3. نصب روی Ubuntu
4. تنظیمات اولیه
5. داشبورد کاربری
6. مستندات API (برای ESP)
7. منطق کنترل رله‌ها
8. آلارم‌ها و نوتیفیکیشن
9. عیب‌یابی

---

## ۱. معماری سیستم

```
[ESP-12E] ←→ [FastAPI Server] ←→ [PostgreSQL]
               ↕                       ↕
            [Redis]              [Sensor Logs]
               ↕
          [Dashboard]
          (مرورگر کاربر)
```

**پشته فناوری:**
- Backend: Python 3.11 + FastAPI
- Database: PostgreSQL (لاگ سنسور، تنظیمات، آلارم)
- Cache: Redis (کش config برای ESP، session کاربر)
- Frontend: HTML/CSS/JS خالص (بدون فریم‌ورک)
- Authentication: Cookie-based session با HMAC

---

## ۲. پیش‌نیازها

- Ubuntu 22.04 یا 24.04
- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- دسترسی اینترنت برای نصب پکیج‌ها

---

## ۳. نصب روی Ubuntu

### روش سریع (اسکریپت خودکار)
```bash
# دانلود و extract پروژه
unzip brooder_server.zip
cd brooder_server

# اجرای اسکریپت نصب
chmod +x install.sh
sudo ./install.sh
```

اسکریپت به‌صورت خودکار:
- PostgreSQL و Redis نصب می‌کند
- دیتابیس و کاربر می‌سازد
- محیط Python مجازی می‌سازد
- سرویس systemd ثبت و اجرا می‌کند
- API_KEY و SECRET_KEY تصادفی تولید می‌کند

### روش دستی
```bash
# ۱. پیش‌نیازها
sudo apt update
sudo apt install -y python3 python3-venv postgresql redis-server

# ۲. دیتابیس
sudo -u postgres psql -c "CREATE USER brooder WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "CREATE DATABASE brooder_db OWNER brooder;"

# ۳. محیط Python
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ۴. تنظیمات
cp .env.example .env
nano .env   # مقادیر را ویرایش کنید

# ۵. اجرا
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## ۴. تنظیمات اولیه (.env)

```env
# اتصال دیتابیس
DATABASE_URL=postgresql+asyncpg://brooder:PASSWORD@localhost:5432/brooder_db

# Redis
REDIS_URL=redis://localhost:6379/0

# کلید رمزنگاری (حتماً تغییر دهید)
SECRET_KEY=یک_رشته_تصادفی_طولانی

# کلید API برای ESP (حتماً تغییر دهید)
API_KEY=کلید_esp_شما

# داشبورد کاربری
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=رمز_عبور_قوی

# مدت اعتبار session (ساعت)
SESSION_EXPIRE_HOURS=12

# تلگرام (اختیاری)
TELEGRAM_BOT_TOKEN=توکن_ربات_تلگرام
TELEGRAM_CHAT_ID=آیدی_چت_تلگرام
```

### ساخت اتاق اول (یک‌بار بعد از نصب)
```bash
curl -X POST http://localhost:8000/api/v1/rooms \
  -H "Content-Type: application/json" \
  -d '{"name": "اتاق جوجه اردک", "age_day_from": 1, "age_day_to": 10}'
```
پاسخ: `{"id": 1, ...}` — شناسه اتاق را یادداشت کنید (معمولاً ۱).

---

## ۵. داشبورد کاربری

### دسترسی
```
http://IP_SERVER:8000
```

### ورود
با نام کاربری و رمز عبور تعریف‌شده در `.env` وارد شوید.
Session به‌مدت `SESSION_EXPIRE_HOURS` ساعت معتبر است.

### صفحات داشبورد

#### 🏠 خانه
- دمای فعلی، دمای هدف، رطوبت، وضعیت کلی
- وضعیت لحظه‌ای ۴ رله (روشن/خاموش)
- نمودار دمای ۱۲ ساعت گذشته
- بروزرسانی خودکار هر ۱۰ ثانیه

#### 🔌 رله‌ها
- کنترل دستی موقت هر ۴ رله (۳۰ ثانیه اعتبار)
- نمایش برنامه دوره‌ای فن

#### 🕐 برنامه دما
- جدول ۶ بازه زمانی
- بازه فعال با رنگ سبز مشخص است
- دکمه ویرایش برای هر بازه

#### ⚙️ تنظیمات
- پارامترهای رطوبت (حداقل/حداکثر/هشدار)
- دمای اضطراری
- برنامه دوره‌ای فن
- تنظیم نوتیفیکیشن تلگرام

#### 🔔 آلارم‌ها
- آلارم‌های فعال با دکمه تأیید
- تاریخچه آلارم‌های ۲۴ ساعت گذشته

---

## ۶. مستندات API (برای ESP)

### احراز هویت
تمام endpoint های ESP نیاز به Header دارند:
```
X-Api-Key: YOUR_API_KEY
```

### دریافت تنظیمات کامل
```http
GET /api/v1/rooms/1/config
X-Api-Key: YOUR_KEY
```

**پاسخ:**
```json
{
  "schedules": [
    {
      "id": 1,
      "period_name": "بامداد_اول",
      "start_hour": 1, "start_minute": 0,
      "end_hour": 3,   "end_minute": 0,
      "target_temp": 33.0,
      "enabled": true
    }
  ],
  "parameters": {
    "humidity_normal_min": 50.0,
    "humidity_normal_max": 68.0,
    "humidity_fan_on": 65.0,
    "humidity_alarm_high": 70.0,
    "humidity_alarm_low": 45.0,
    "temp_emergency_low": 27.0,
    "temp_emergency_high": 38.0,
    "element_activate_diff": 3.0,
    "temp_tolerance": 0.5
  },
  "fan_schedule": {
    "interval_minutes": 120,
    "duration_minutes": 5,
    "enabled": true,
    "disable_on_emergency": true
  },
  "server_time": "2024-01-15T14:30:00+03:30"
}
```

### ارسال داده سنسور (هر ۳۰ ثانیه)
```http
POST /api/v1/rooms/1/sensor
X-Api-Key: YOUR_KEY
Content-Type: application/json

{
  "temperature": 32.5,
  "humidity": 58.2,
  "relay_state": {
    "ch1": true,
    "ch2": false,
    "ch3": false,
    "ch4": false
  }
}
```

### بررسی دستور دستی (هر ۱۵ ثانیه)
```http
GET /api/v1/rooms/1/manual-command
X-Api-Key: YOUR_KEY
```
پاسخ بدون دستور: `{"has_command": false}`
پاسخ با دستور: `{"has_command": true, "command": {"channel": 2, "state": true, "reason": "..."}}`

---

## ۷. منطق کنترل رله‌ها

### نگاشت رله‌ها
| کانال | دستگاه | کاربرد |
|-------|--------|--------|
| CH1 | هر دو لامپ ۲۰۰W | گرمایش اصلی |
| CH2 | لامپ ۱۰۰W | گرمایش نگهداری |
| CH3 | المنت اضطراری | گرمایش اضطراری |
| CH4 | فن سایلنت | تهویه |

### جدول تصمیم‌گیری
| شرایط دما | CH1 | CH2 | CH3 | CH4 |
|-----------|-----|-----|-----|-----|
| اضطراری سرد (≤ temp_emergency_low) | ✅ | ✅ | ✅ | ❌ |
| خیلی سرد (diff > element_activate_diff) | ✅ | ✅ | ✅ | auto |
| سرد (diff > tolerance) | ✅ | ✅ | ❌ | auto |
| نزدیک هدف (±tolerance) | ❌ | ✅ | ❌ | auto |
| گرم (temp > target+tolerance) | ❌ | ❌ | ❌ | auto |
| اضطراری گرم (≥ temp_emergency_high) | ❌ | ❌ | ❌ | ✅ |

**فن (CH4) — منطق:**
1. اگر دمای اضطراری سرد → فن خاموش (اولویت اول)
2. اگر رطوبت ≥ humidity_fan_on → فن روشن فوری
3. اگر سیکل دوره‌ای فرا رسیده → فن روشن به‌مدت duration_minutes

### برنامه دمایی پیش‌فرض
| بازه | ساعت | دما |
|------|------|-----|
| بامداد اول | ۰۱:۰۰ — ۰۳:۰۰ | ۳۳°C |
| بامداد دوم | ۰۳:۰۰ — ۰۶:۰۰ | ۳۴°C |
| صبح | ۰۶:۰۰ — ۱۰:۰۰ | ۳۱°C |
| روز | ۱۰:۰۰ — ۱۶:۰۰ | ۳۰°C |
| عصر | ۱۶:۰۰ — ۲۰:۰۰ | ۳۱°C |
| شب | ۲۰:۰۰ — ۰۱:۰۰ | ۳۲°C |

---

## ۸. آلارم‌ها و نوتیفیکیشن

### انواع آلارم
| نوع | شرط | پیام |
|-----|-----|------|
| HUMIDITY_HIGH | رطوبت ≥ humidity_alarm_high | رطوبت بالا |
| HUMIDITY_LOW | رطوبت ≤ humidity_alarm_low | رطوبت پایین |
| TEMP_EMERGENCY_LOW | دما ≤ temp_emergency_low | دمای اضطراری پایین |
| TEMP_EMERGENCY_HIGH | دما ≥ temp_emergency_high | دمای اضطراری بالا |

### تلگرام
1. یک ربات تلگرام بسازید (از @BotFather)
2. توکن را در `.env` قرار دهید
3. Chat ID را (از @userinfobot) در `.env` قرار دهید
4. در تنظیمات داشبورد نوتیفیکیشن را فعال کنید

---

## ۹. عیب‌یابی

### سرویس راه‌اندازی نمی‌شود
```bash
sudo systemctl status brooder
sudo journalctl -u brooder -n 50
```

### مشکل اتصال به دیتابیس
```bash
sudo -u postgres psql -c "\l"   # لیست دیتابیس‌ها
sudo systemctl status postgresql
```

### ESP وصل نمی‌شود
- API_KEY در `.env` و در ESP باید یکسان باشد
- پورت ۸۰۰۰ در فایروال باز باشد: `sudo ufw allow 8000`

### ریست کردن رمز داشبورد
```bash
sudo nano /opt/brooder_server/.env
# DASHBOARD_PASSWORD را تغییر دهید
sudo systemctl restart brooder
```

### دستورات مفید
```bash
# وضعیت سرویس
sudo systemctl status brooder

# لاگ real-time
sudo journalctl -u brooder -f

# ری‌استارت
sudo systemctl restart brooder

# Swagger API
http://IP:8000/api/docs
```
# brooder
