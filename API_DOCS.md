# مستندات API سرور گرم‌خانه

## آدرس پایه
```
http://YOUR_SERVER_IP:8000/api/v1
```
مستندات Swagger: `http://YOUR_SERVER_IP:8000/docs`

---

## احراز هویت ESP
همه endpoint های ESP نیاز به Header زیر دارند:
```
X-Api-Key: YOUR_API_KEY
```

---

## endpoints اصلی

### ۱. ایجاد اتاق
```http
POST /rooms
Content-Type: application/json

{"name": "اتاق جوجه اردک", "age_day_from": 1, "age_day_to": 10}
```

### ۲. دریافت تنظیمات کامل (برای ESP)
```http
GET /rooms/{room_id}/config
X-Api-Key: YOUR_KEY
```
**پاسخ:**
```json
{
  "schedules": [...],
  "parameters": {...},
  "fan_schedule": {...},
  "server_time": "2024-01-15T14:30:00+03:30"
}
```

### ۳. ارسال داده سنسور (از ESP)
```http
POST /rooms/{room_id}/sensor
X-Api-Key: YOUR_KEY
Content-Type: application/json

{
  "temperature": 32.5,
  "humidity": 58.2,
  "relay_state": {"ch1": true, "ch2": false, "ch3": false, "ch4": false}
}
```

### ۴. تغییر برنامه دمایی
```http
PATCH /schedules/{schedule_id}
Content-Type: application/json

{"target_temp": 33.5, "start_hour": 1, "end_hour": 3}
```

### ۵. تغییر پارامترها
```http
PATCH /rooms/{room_id}/parameters
Content-Type: application/json

{
  "humidity_alarm_high": 72,
  "temp_emergency_low": 26,
  "element_activate_diff": 4
}
```

### ۶. تغییر برنامه فن
```http
PATCH /rooms/{room_id}/fan-schedule
Content-Type: application/json

{"interval_minutes": 90, "duration_minutes": 7}
```

### ۷. کنترل دستی رله
```http
POST /rooms/{room_id}/relay/command
Content-Type: application/json

{"channel": 3, "state": true, "reason": "تست المنت اضطراری"}
```

### ۸. وضعیت real-time اتاق
```http
GET /rooms/{room_id}/status
```

### ۹. لاگ سنسور
```http
GET /rooms/{room_id}/logs?limit=100
```

### ۱۰. آلارم‌های فعال
```http
GET /rooms/{room_id}/alarms?resolved=false
```

### ۱۱. تأیید آلارم
```http
PATCH /alarms/{alarm_id}/resolve
```

---

## منطق رله‌ها

| شرایط | CH1 (200W) | CH2 (100W) | CH3 (المنت) | CH4 (فن) |
|--------|-----------|-----------|-------------|---------|
| دمای اضطراری پایین | ✅ | ✅ | ✅ | ❌ |
| خیلی سرد (diff > element_diff) | ✅ | ✅ | ✅ | - |
| سرد (diff > tolerance) | ✅ | ✅ | ❌ | - |
| نزدیک هدف | ❌ | ✅ | ❌ | - |
| گرم | ❌ | ❌ | ❌ | - |
| دمای اضطراری بالا | ❌ | ❌ | ❌ | ✅ |
| رطوبت > fan_on | - | - | - | ✅ |
| سیکل دوره‌ای فن | - | - | - | ✅ |
