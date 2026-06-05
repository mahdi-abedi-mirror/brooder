"""
روت‌های اصلی API
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import pytz
import json

from app.db.session import get_db
from app.db.redis import get_redis
from app.models.models import Room, Schedule, Parameter, FanSchedule, SensorLog, Alarm, RelayLog
from app.schemas.schemas import (
    RoomCreate, RoomOut,
    ScheduleCreate, ScheduleUpdate, ScheduleOut,
    ParameterUpdate, ParameterOut,
    FanScheduleUpdate, FanScheduleOut,
    SensorDataIn, SensorLogOut,
    ESPConfigOut, RelayCommand,
    RoomStatusOut, AlarmOut,
)
from app.services.control import (
    get_current_target_temp, calculate_relay_commands,
    check_and_fire_alarms, TEHRAN_TZ
)
from app.core.config import settings

router = APIRouter()


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="API key نامعتبر")


# ══════════════════════════════════════════
#  ROOMS
# ══════════════════════════════════════════

@router.post("/rooms", response_model=RoomOut, tags=["Rooms"])
async def create_room(data: RoomCreate, db: AsyncSession = Depends(get_db)):
    room = Room(**data.model_dump())
    db.add(room)
    await db.flush()

    # پارامترهای پیش‌فرض
    params = Parameter(room_id=room.id)
    fan_sch = FanSchedule(room_id=room.id)
    db.add(params)
    db.add(fan_sch)

    # برنامه دمایی پیش‌فرض (۶ بازه)
    default_schedules = [
        {"period_name": "بامداد_اول", "start_hour": 1,  "end_hour": 3,  "target_temp": 33},
        {"period_name": "بامداد_دوم", "start_hour": 3,  "end_hour": 6,  "target_temp": 34},
        {"period_name": "صبح",        "start_hour": 6,  "end_hour": 10, "target_temp": 31},
        {"period_name": "روز",        "start_hour": 10, "end_hour": 16, "target_temp": 30},
        {"period_name": "عصر",        "start_hour": 16, "end_hour": 20, "target_temp": 31},
        {"period_name": "شب",         "start_hour": 20, "end_hour": 1,  "target_temp": 32},
    ]
    for s in default_schedules:
        db.add(Schedule(room_id=room.id, **s))

    await db.commit()
    return room


@router.get("/rooms", response_model=list[RoomOut], tags=["Rooms"])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).where(Room.active == True))
    return result.scalars().all()


# ══════════════════════════════════════════
#  SCHEDULES
# ══════════════════════════════════════════

@router.get("/rooms/{room_id}/schedules", response_model=list[ScheduleOut], tags=["Schedules"])
async def get_schedules(room_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Schedule).where(Schedule.room_id == room_id).order_by(Schedule.start_hour)
    )
    return result.scalars().all()


@router.post("/rooms/{room_id}/schedules", response_model=ScheduleOut, tags=["Schedules"])
async def create_schedule(room_id: int, data: ScheduleCreate, db: AsyncSession = Depends(get_db)):
    sch = Schedule(room_id=room_id, **data.model_dump())
    db.add(sch)
    await db.commit()
    await db.refresh(sch)
    return sch


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut, tags=["Schedules"])
async def update_schedule(schedule_id: int, data: ScheduleUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    sch = result.scalar_one_or_none()
    if not sch:
        raise HTTPException(404, "برنامه یافت نشد")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(sch, k, v)
    await db.commit()
    await db.refresh(sch)
    return sch


@router.delete("/schedules/{schedule_id}", tags=["Schedules"])
async def delete_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    sch = result.scalar_one_or_none()
    if not sch:
        raise HTTPException(404, "برنامه یافت نشد")
    await db.delete(sch)
    await db.commit()
    return {"message": "حذف شد"}


# ══════════════════════════════════════════
#  PARAMETERS
# ══════════════════════════════════════════

@router.get("/rooms/{room_id}/parameters", response_model=ParameterOut, tags=["Parameters"])
async def get_parameters(room_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Parameter).where(Parameter.room_id == room_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "پارامتر یافت نشد")
    return p


@router.patch("/rooms/{room_id}/parameters", response_model=ParameterOut, tags=["Parameters"])
async def update_parameters(room_id: int, data: ParameterUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Parameter).where(Parameter.room_id == room_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "پارامتر یافت نشد")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    # کش Redis رو invalidate کن
    redis = await get_redis()
    await redis.delete(f"config:{room_id}")
    return p


# ══════════════════════════════════════════
#  FAN SCHEDULE
# ══════════════════════════════════════════

@router.get("/rooms/{room_id}/fan-schedule", response_model=FanScheduleOut, tags=["Fan"])
async def get_fan_schedule(room_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FanSchedule).where(FanSchedule.room_id == room_id))
    fs = result.scalar_one_or_none()
    if not fs:
        raise HTTPException(404, "برنامه فن یافت نشد")
    return fs


@router.patch("/rooms/{room_id}/fan-schedule", response_model=FanScheduleOut, tags=["Fan"])
async def update_fan_schedule(room_id: int, data: FanScheduleUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FanSchedule).where(FanSchedule.room_id == room_id))
    fs = result.scalar_one_or_none()
    if not fs:
        raise HTTPException(404, "برنامه فن یافت نشد")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(fs, k, v)
    await db.commit()
    await db.refresh(fs)
    redis = await get_redis()
    await redis.delete(f"config:{room_id}")
    return fs


# ══════════════════════════════════════════
#  ESP ENDPOINTS
# ══════════════════════════════════════════

@router.get("/rooms/{room_id}/config", response_model=ESPConfigOut, tags=["ESP"])
async def get_esp_config(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
):
    """ESP این endpoint رو می‌زند تا آخرین تنظیمات رو دریافت کنه"""
    redis = await get_redis()
    cached = await redis.get(f"config:{room_id}")
    if cached:
        return json.loads(cached)

    schedules_r = await db.execute(select(Schedule).where(Schedule.room_id == room_id))
    params_r = await db.execute(select(Parameter).where(Parameter.room_id == room_id))
    fan_r = await db.execute(select(FanSchedule).where(FanSchedule.room_id == room_id))

    schedules = schedules_r.scalars().all()
    params = params_r.scalar_one_or_none()
    fan_sch = fan_r.scalar_one_or_none()

    if not params or not fan_sch:
        raise HTTPException(404, "اتاق یا تنظیمات یافت نشد")

    now_tehran = datetime.now(TEHRAN_TZ).isoformat()
    config = ESPConfigOut(
        schedules=[ScheduleOut.model_validate(s) for s in schedules],
        parameters=ParameterOut.model_validate(params),
        fan_schedule=FanScheduleOut.model_validate(fan_sch),
        server_time=now_tehran,
    )

    # کش 60 ثانیه
    await redis.setex(f"config:{room_id}", 60, config.model_dump_json())
    return config


@router.post("/rooms/{room_id}/sensor", tags=["ESP"])
async def receive_sensor_data(
    room_id: int,
    data: SensorDataIn,
    db: AsyncSession = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
):
    """
    ESP هر N ثانیه داده سنسور رو اینجا ارسال می‌کند.
    سرور: لاگ می‌کند + آلارم بررسی می‌کند + آخرین وضعیت در Redis ذخیره می‌کند
    """
    params_r = await db.execute(select(Parameter).where(Parameter.room_id == room_id))
    params = params_r.scalar_one_or_none()
    if not params:
        raise HTTPException(404, "اتاق یافت نشد")

    # ذخیره لاگ
    log = SensorLog(
        room_id=room_id,
        temperature=data.temperature,
        humidity=data.humidity,
        relay_state=data.relay_state,
    )
    db.add(log)

    # آخرین وضعیت در Redis (برای داشبورد real-time)
    redis = await get_redis()
    await redis.setex(
        f"status:{room_id}",
        300,
        json.dumps({
            "temperature": data.temperature,
            "humidity": data.humidity,
            "relay_state": data.relay_state,
            "last_seen": datetime.utcnow().isoformat(),
        }),
    )

    # بررسی آلارم
    alarms_fired = await check_and_fire_alarms(
        db, room_id, data.temperature, data.humidity, params
    )

    await db.commit()

    return {
        "status": "ok",
        "alarms_fired": alarms_fired,
        "logged_at": datetime.utcnow().isoformat(),
    }


@router.post("/rooms/{room_id}/relay/command", tags=["ESP"])
async def manual_relay_command(
    room_id: int,
    cmd: RelayCommand,
    db: AsyncSession = Depends(get_db),
):
    """کنترل دستی رله از داشبورد"""
    log = RelayLog(
        room_id=room_id,
        channel=cmd.channel,
        state=cmd.state,
        reason=cmd.reason,
    )
    db.add(log)
    await db.commit()

    # در Redis یک دستور موقت برای ESP بذار
    redis = await get_redis()
    await redis.setex(
        f"manual_cmd:{room_id}",
        30,  # 30 ثانیه اعتبار
        json.dumps({"channel": cmd.channel, "state": cmd.state, "reason": cmd.reason}),
    )
    return {"status": "ok", "message": f"دستور CH{cmd.channel} → {'روشن' if cmd.state else 'خاموش'} ارسال شد"}


@router.get("/rooms/{room_id}/manual-command", tags=["ESP"])
async def get_manual_command(
    room_id: int,
    x_api_key: str = Depends(verify_api_key),
):
    """ESP این رو poll می‌کند تا ببیند دستور دستی وجود دارد یا نه"""
    redis = await get_redis()
    cmd = await redis.get(f"manual_cmd:{room_id}")
    if cmd:
        await redis.delete(f"manual_cmd:{room_id}")
        return {"has_command": True, "command": json.loads(cmd)}
    return {"has_command": False}


# ══════════════════════════════════════════
#  MONITORING & ALARMS
# ══════════════════════════════════════════

@router.get("/rooms/{room_id}/status", response_model=RoomStatusOut, tags=["Monitoring"])
async def get_room_status(room_id: int, db: AsyncSession = Depends(get_db)):
    redis = await get_redis()
    cached_status = await redis.get(f"status:{room_id}")

    last_temp = last_hum = last_relay = last_seen = None
    if cached_status:
        s = json.loads(cached_status)
        last_temp = s.get("temperature")
        last_hum = s.get("humidity")
        last_relay = s.get("relay_state")
        last_seen = datetime.fromisoformat(s["last_seen"]) if s.get("last_seen") else None

    # دمای هدف فعلی
    schedules_r = await db.execute(select(Schedule).where(and_(Schedule.room_id == room_id, Schedule.enabled == True)))
    schedules = schedules_r.scalars().all()
    now_tehran = datetime.now(TEHRAN_TZ)
    target_temp = get_current_target_temp(schedules, now_tehran)

    # تعداد آلارم‌های فعال
    alarms_r = await db.execute(
        select(Alarm).where(and_(Alarm.room_id == room_id, Alarm.resolved == False))
    )
    active_alarms = len(alarms_r.scalars().all())

    room_r = await db.execute(select(Room).where(Room.id == room_id))
    room = room_r.scalar_one_or_none()

    return RoomStatusOut(
        room_id=room_id,
        room_name=room.name if room else "",
        last_temperature=last_temp,
        last_humidity=last_hum,
        last_relay_state=last_relay,
        last_seen=last_seen,
        active_alarms=active_alarms,
        current_target_temp=target_temp,
    )


@router.get("/rooms/{room_id}/logs", response_model=list[SensorLogOut], tags=["Monitoring"])
async def get_sensor_logs(room_id: int, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SensorLog)
        .where(SensorLog.room_id == room_id)
        .order_by(desc(SensorLog.recorded_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/rooms/{room_id}/alarms", response_model=list[AlarmOut], tags=["Monitoring"])
async def get_alarms(room_id: int, resolved: bool = False, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Alarm)
        .where(and_(Alarm.room_id == room_id, Alarm.resolved == resolved))
        .order_by(desc(Alarm.created_at))
    )
    return result.scalars().all()


@router.patch("/alarms/{alarm_id}/resolve", response_model=AlarmOut, tags=["Monitoring"])
async def resolve_alarm(alarm_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()
    if not alarm:
        raise HTTPException(404, "آلارم یافت نشد")
    alarm.resolved = True
    alarm.resolved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(alarm)
    return alarm
