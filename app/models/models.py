from datetime import datetime
from sqlalchemy import (
    Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age_day_from: Mapped[int] = mapped_column(Integer, default=1)
    age_day_to: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="room", cascade="all, delete")
    parameters: Mapped["Parameter"] = relationship(back_populates="room", uselist=False, cascade="all, delete")
    fan_schedule: Mapped["FanSchedule"] = relationship(back_populates="room", uselist=False, cascade="all, delete")
    sensor_logs: Mapped[list["SensorLog"]] = relationship(back_populates="room", cascade="all, delete")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="room", cascade="all, delete")
    relay_logs: Mapped[list["RelayLog"]] = relationship(back_populates="room", cascade="all, delete")


class Schedule(Base):
    """برنامه دمایی برای هر بازه زمانی"""
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    period_name: Mapped[str] = mapped_column(String(50))  # e.g. "بامداد_اول"
    start_hour: Mapped[int] = mapped_column(Integer)       # 0-23
    start_minute: Mapped[int] = mapped_column(Integer, default=0)
    end_hour: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer, default=0)
    target_temp: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    room: Mapped["Room"] = relationship(back_populates="schedules")


class Parameter(Base):
    """تمام پارامترهای قابل تنظیم از سرور"""
    __tablename__ = "parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), unique=True, nullable=False)

    # رطوبت
    humidity_normal_min: Mapped[float] = mapped_column(Float, default=50.0)
    humidity_normal_max: Mapped[float] = mapped_column(Float, default=68.0)
    humidity_fan_on: Mapped[float] = mapped_column(Float, default=65.0)
    humidity_alarm_high: Mapped[float] = mapped_column(Float, default=70.0)
    humidity_alarm_low: Mapped[float] = mapped_column(Float, default=45.0)

    # دما اضطراری
    temp_emergency_low: Mapped[float] = mapped_column(Float, default=27.0)
    temp_emergency_high: Mapped[float] = mapped_column(Float, default=38.0)

    # المنت اضطراری: وقتی دما چند درجه زیر هدف بود فعال شود
    element_activate_diff: Mapped[float] = mapped_column(Float, default=3.0)

    # تلورانس دما برای رله‌ها
    temp_tolerance: Mapped[float] = mapped_column(Float, default=0.5)

    # گرمایش: CH1=لامپ‌های 200W، CH2=لامپ 100W، CH3=المنت، CH4=فن
    relay_ch1_label: Mapped[str] = mapped_column(String(50), default="لامپ 200W")
    relay_ch2_label: Mapped[str] = mapped_column(String(50), default="لامپ 100W")
    relay_ch3_label: Mapped[str] = mapped_column(String(50), default="المنت اضطراری")
    relay_ch4_label: Mapped[str] = mapped_column(String(50), default="فن سایلنت")

    # نوتیفیکیشن تلگرام
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    room: Mapped["Room"] = relationship(back_populates="parameters")


class FanSchedule(Base):
    """برنامه دوره‌ای فن برای کنترل آمونیاک"""
    __tablename__ = "fan_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), unique=True, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=120)  # هر چند دقیقه یکبار
    duration_minutes: Mapped[int] = mapped_column(Integer, default=5)    # چند دقیقه روشن باشد
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # در حالت اضطراری دما فن اصلاً کار نکند
    disable_on_emergency: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    room: Mapped["Room"] = relationship(back_populates="fan_schedule")


class SensorLog(Base):
    """لاگ دما و رطوبت هر X ثانیه از ESP"""
    __tablename__ = "sensor_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    relay_state: Mapped[dict] = mapped_column(JSON)  # {"ch1":true,"ch2":false,"ch3":false,"ch4":false}
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    room: Mapped["Room"] = relationship(back_populates="sensor_logs")


class Alarm(Base):
    """آلارم‌های نوتیفیکیشن"""
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    alarm_type: Mapped[str] = mapped_column(String(50))
    # نوع: HUMIDITY_HIGH | HUMIDITY_LOW | TEMP_EMERGENCY_LOW | TEMP_EMERGENCY_HIGH
    value: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    room: Mapped["Room"] = relationship(back_populates="alarms")


class RelayLog(Base):
    """لاگ تغییر وضعیت رله‌ها"""
    __tablename__ = "relay_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    channel: Mapped[int] = mapped_column(Integer)   # 1-4
    state: Mapped[bool] = mapped_column(Boolean)    # True=ON, False=OFF
    reason: Mapped[str] = mapped_column(String(200))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    room: Mapped["Room"] = relationship(back_populates="relay_logs")
