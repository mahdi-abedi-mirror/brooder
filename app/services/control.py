"""
سرویس منطق کنترل گرم‌خانه
این سرویس تصمیم می‌گیرد کدام رله‌ها باید روشن یا خاموش باشند
"""
from datetime import datetime
import pytz
import json
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.models import Schedule, Parameter, FanSchedule, Alarm, RelayLog, SensorLog
from app.core.config import settings


TEHRAN_TZ = pytz.timezone("Asia/Tehran")


def get_current_target_temp(schedules: list, now: datetime) -> float | None:
    """دمای هدف را بر اساس ساعت فعلی از جدول برنامه پیدا می‌کند"""
    current_minutes = now.hour * 60 + now.minute

    for sch in schedules:
        if not sch.enabled:
            continue
        start = sch.start_hour * 60 + sch.start_minute
        end = sch.end_hour * 60 + sch.end_minute

        # اگر بازه از نیمه‌شب رد می‌شود (مثلاً 20:00 تا 01:00)
        if start > end:
            if current_minutes >= start or current_minutes < end:
                return sch.target_temp
        else:
            if start <= current_minutes < end:
                return sch.target_temp
    return None


def calculate_relay_commands(
    temperature: float,
    humidity: float,
    target_temp: float,
    params,
    fan_sch,
    last_fan_on: datetime | None,
    now: datetime,
) -> dict:
    """
    محاسبه وضعیت رله‌ها بر اساس تمام پارامترها
    
    برمی‌گرداند:
        {
          "ch1": bool,  # لامپ‌های 200W
          "ch2": bool,  # لامپ 100W
          "ch3": bool,  # المنت اضطراری
          "ch4": bool,  # فن
          "reason": str
        }
    """
    tol = params.temp_tolerance
    diff = target_temp - temperature  # مثبت = سردتر از هدف، منفی = گرم‌تر

    # ── وضعیت اضطراری دما ──────────────────────────────
    is_emergency_cold = temperature <= params.temp_emergency_low
    is_emergency_hot = temperature >= params.temp_emergency_high

    if is_emergency_cold:
        # همه گرماها روشن، فن خاموش
        return {
            "ch1": True, "ch2": True, "ch3": True, "ch4": False,
            "reason": f"اضطراری سرما: {temperature}°C"
        }

    if is_emergency_hot:
        # همه گرماها خاموش، فن روشن
        return {
            "ch1": False, "ch2": False, "ch3": False, "ch4": True,
            "reason": f"اضطراری گرما: {temperature}°C"
        }

    # ── کنترل گرمایش ───────────────────────────────────
    ch1 = False  # لامپ‌های 200W
    ch2 = False  # لامپ 100W
    ch3 = False  # المنت اضطراری

    if diff > params.element_activate_diff:
        # خیلی سرد: همه گرماها روشن
        ch1, ch2, ch3 = True, True, True
        reason = f"خیلی سرد ({temperature}°C < {target_temp - params.element_activate_diff}°C)"
    elif diff > tol:
        # سرد: 200W + 100W روشن
        ch1, ch2 = True, True
        reason = f"سرد ({temperature}°C → هدف {target_temp}°C)"
    elif diff > -tol:
        # نزدیک هدف: فقط 100W
        ch2 = True
        reason = f"نگهداری ({temperature}°C ≈ {target_temp}°C)"
    else:
        # گرم‌تر از هدف: همه خاموش
        reason = f"دما کافی ({temperature}°C)"

    # ── کنترل فن ───────────────────────────────────────
    ch4 = False
    fan_reason = ""

    # اگر اضطراری سرما بود فن خاموش (بالا handle شد)
    # رطوبت بالا → فن روشن فوری
    if humidity >= params.humidity_fan_on:
        ch4 = True
        fan_reason = f"رطوبت بالا ({humidity}%)"
    elif fan_sch and fan_sch.enabled:
        # فن دوره‌ای برای کنترل آمونیاک
        if last_fan_on is None:
            # اولین بار
            ch4 = True
            fan_reason = "اولین سیکل فن"
        else:
            elapsed = (now - last_fan_on).total_seconds() / 60
            if elapsed >= fan_sch.interval_minutes:
                ch4 = True
                fan_reason = f"سیکل دوره‌ای ({elapsed:.0f} دقیقه گذشته)"

    return {
        "ch1": ch1, "ch2": ch2, "ch3": ch3, "ch4": ch4,
        "reason": reason + (f" | فن: {fan_reason}" if fan_reason else "")
    }


async def check_and_fire_alarms(
    db: AsyncSession,
    room_id: int,
    temperature: float,
    humidity: float,
    params,
) -> list[str]:
    """بررسی شرایط آلارم و ثبت + ارسال نوتیفیکیشن"""
    fired = []

    alarm_conditions = []

    if humidity >= params.humidity_alarm_high:
        alarm_conditions.append(("HUMIDITY_HIGH", humidity, f"رطوبت بالا: {humidity}% (حد مجاز: {params.humidity_alarm_high}%)"))
    if humidity <= params.humidity_alarm_low:
        alarm_conditions.append(("HUMIDITY_LOW", humidity, f"رطوبت پایین: {humidity}% (حد مجاز: {params.humidity_alarm_low}%)"))
    if temperature <= params.temp_emergency_low:
        alarm_conditions.append(("TEMP_EMERGENCY_LOW", temperature, f"دمای اضطراری پایین: {temperature}°C (حد: {params.temp_emergency_low}°C)"))
    if temperature >= params.temp_emergency_high:
        alarm_conditions.append(("TEMP_EMERGENCY_HIGH", temperature, f"دمای اضطراری بالا: {temperature}°C (حد: {params.temp_emergency_high}°C)"))

    for alarm_type, value, message in alarm_conditions:
        # بررسی آلارم مشابه فعال (resolve نشده)
        existing = await db.execute(
            select(Alarm).where(
                and_(
                    Alarm.room_id == room_id,
                    Alarm.alarm_type == alarm_type,
                    Alarm.resolved == False,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue  # آلارم مشابه قبلاً ثبت شده

        alarm = Alarm(
            room_id=room_id,
            alarm_type=alarm_type,
            value=value,
            message=message,
        )
        db.add(alarm)
        fired.append(message)

        if params.notifications_enabled:
            await send_telegram_notification(message)

    return fired


async def send_telegram_notification(message: str):
    """ارسال نوتیفیکیشن تلگرام"""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": f"🚨 آلارم گرم‌خانه\n{message}",
                "parse_mode": "HTML",
            })
    except Exception:
        pass  # نوتیفیکیشن شکست نباید کل سیستم رو متوقف کنه
