# data/data_manager.py
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any
from schedule_manager.models.employee import Employee
from schedule_manager.models.schedule import DailySchedule

# 프로젝트 루트 = .../schedule_manager
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
EMP_FILE = DATA_DIR / "employees.json"
SCH_FILE = DATA_DIR / "schedules.json"
NOTES_FILE = DATA_DIR / "notes.txt"

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def _safe_json_load(path: Path, default):
    if not path.exists():
        return default
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default

def _safe_json_save(path: Path, data):
    _ensure_data_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

# ---------- 직원 ----------
def _emp_to_dict(e) -> Dict[str, Any]:
    # Employee 인스턴스이든, dict 비슷한 객체든 안전 변환
    if isinstance(e, Employee):
        return {
            "id": e.id,
            "name": e.name,
            "role": e.role,
            "skill_level": e.skill_level,         # "C"/"N" 또는 "cook"/"nocook"
            "home_branch": e.home_branch,         # "OS"/"HC"
            "fixed_holidays": e.fixed_holidays or [],
            "holiday_requests": getattr(e, "holiday_requests", []) or [],
            "min_shifts_per_week": getattr(e, "min_shifts_per_week", 0),
            "max_shifts_per_week": getattr(e, "max_shifts_per_week", 6),
        }
    # _mk_employee로 만든 객체 지원
    if hasattr(e, "__dict__"):
        d = e.__dict__.copy()
        d.setdefault("fixed_holidays", [])
        d.setdefault("holiday_requests", [])
        d.setdefault("min_shifts_per_week", 0)
        d.setdefault("max_shifts_per_week", 6)
        return d
    # dict인 경우
    if isinstance(e, dict):
        d = e.copy()
        d.setdefault("fixed_holidays", [])
        d.setdefault("holiday_requests", [])
        d.setdefault("min_shifts_per_week", 0)
        d.setdefault("max_shifts_per_week", 6)
        return d
    raise TypeError(f"Unsupported employee type: {type(e)}")

def load_employees() -> List[Employee]:
    data = _safe_json_load(EMP_FILE, default=[])
    return [Employee(**item) for item in data]

def save_employees(employees: List[Employee]):
    payload = [_emp_to_dict(e) for e in employees]
    _safe_json_save(EMP_FILE, payload)

# ---------- 스케줄 ----------
def load_schedules() -> Dict[str, DailySchedule]:
    data = _safe_json_load(SCH_FILE, default={})
    return {date: DailySchedule.from_dict(val) for date, val in data.items()}

def save_schedules(schedules: Dict[str, DailySchedule]):
    payload = {date: sch.to_dict() for date, sch in schedules.items()}
    _safe_json_save(SCH_FILE, payload)

# ---------- 노트 ----------
def load_notes() -> str:
    """노트 텍스트를 로드. 없으면 빈 문자열 반환."""
    if not NOTES_FILE.exists():
        return ""
    try:
        return NOTES_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""

def save_notes(text: str) -> None:
    """노트를 저장. data/가 없으면 생성."""
    _ensure_data_dir()
    NOTES_FILE.write_text(text or "", encoding="utf-8")