from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Room ──────────────────────────────────────────────
class RoomCreate(BaseModel):
    name: str
    age_day_from: int = 1
    age_day_to: int = 10

class RoomOut(BaseModel):
    id: int
    name: str
    age_day_from: int
    age_day_to: int
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Schedule ──────────────────────────────────────────
class ScheduleCreate(BaseModel):
    period_name: str
    start_hour: int = Field(ge=0, le=23)
    start_minute: int = Field(default=0, ge=0, le=59)
    end_hour: int = Field(ge=0, le=23)
    end_minute: int = Field(default=0, ge=0, le=59)
    target_temp: float = Field(ge=20.0, le=45.0)
    enabled: bool = True

class ScheduleUpdate(BaseModel):
    period_name: Optional[str] = None
    start_hour: Optional[int] = Field(default=None, ge=0, le=23)
    start_minute: Optional[int] = Field(default=None, ge=0, le=59)
    end_hour: Optional[int] = Field(default=None, ge=0, le=23)
    end_minute: Optional[int] = Field(default=None, ge=0, le=59)
    target_temp: Optional[float] = Field(default=None, ge=20.0, le=45.0)
    enabled: Optional[bool] = None

class ScheduleOut(BaseModel):
    id: int
    room_id: int
    period_name: str
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    target_temp: float
    enabled: bool
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Parameter ─────────────────────────────────────────
class ParameterUpdate(BaseModel):
    humidity_normal_min: Optional[float] = Field(default=None, ge=0, le=100)
    humidity_normal_max: Optional[float] = Field(default=None, ge=0, le=100)
    humidity_fan_on: Optional[float] = Field(default=None, ge=0, le=100)
    humidity_alarm_high: Optional[float] = Field(default=None, ge=0, le=100)
    humidity_alarm_low: Optional[float] = Field(default=None, ge=0, le=100)
    temp_emergency_low: Optional[float] = Field(default=None, ge=0, le=50)
    temp_emergency_high: Optional[float] = Field(default=None, ge=0, le=50)
    element_activate_diff: Optional[float] = Field(default=None, ge=0.5, le=10)
    temp_tolerance: Optional[float] = Field(default=None, ge=0.1, le=5)
    notifications_enabled: Optional[bool] = None

class ParameterOut(BaseModel):
    id: int
    room_id: int
    humidity_normal_min: float
    humidity_normal_max: float
    humidity_fan_on: float
    humidity_alarm_high: float
    humidity_alarm_low: float
    temp_emergency_low: float
    temp_emergency_high: float
    element_activate_diff: float
    temp_tolerance: float
    relay_ch1_label: str
    relay_ch2_label: str
    relay_ch3_label: str
    relay_ch4_label: str
    notifications_enabled: bool
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Fan Schedule ──────────────────────────────────────
class FanScheduleUpdate(BaseModel):
    interval_minutes: Optional[int] = Field(default=None, ge=10, le=1440)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=60)
    enabled: Optional[bool] = None
    disable_on_emergency: Optional[bool] = None

class FanScheduleOut(BaseModel):
    id: int
    room_id: int
    interval_minutes: int
    duration_minutes: int
    enabled: bool
    disable_on_emergency: bool
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Sensor Data (از ESP دریافت می‌شود) ───────────────
class SensorDataIn(BaseModel):
    temperature: float
    humidity: float
    relay_state: dict  # {"ch1": true, "ch2": false, ...}

class SensorLogOut(BaseModel):
    id: int
    room_id: int
    temperature: float
    humidity: float
    relay_state: dict
    recorded_at: datetime
    model_config = {"from_attributes": True}


# ── Config برای ESP (پاسخ کامل تنظیمات) ─────────────
class ESPConfigOut(BaseModel):
    schedules: list[ScheduleOut]
    parameters: ParameterOut
    fan_schedule: FanScheduleOut
    server_time: str  # ISO format


# ── Alarm ─────────────────────────────────────────────
class AlarmOut(BaseModel):
    id: int
    room_id: int
    alarm_type: str
    value: float
    message: str
    resolved: bool
    resolved_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Relay Manual Control ──────────────────────────────
class RelayCommand(BaseModel):
    channel: int = Field(ge=1, le=4)
    state: bool
    reason: str = "دستور دستی از سرور"


# ── Dashboard / Status ────────────────────────────────
class RoomStatusOut(BaseModel):
    room_id: int
    room_name: str
    last_temperature: Optional[float]
    last_humidity: Optional[float]
    last_relay_state: Optional[dict]
    last_seen: Optional[datetime]
    active_alarms: int
    current_target_temp: Optional[float]
