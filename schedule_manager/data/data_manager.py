# data/data_manager.py
import json
import os
from schedule_manager.models.employee import Employee
from schedule_manager.models.schedule import DailySchedule

DATA_FILE = "data/employees.json"
SCHEDULE_FILE = "data/schedules.json"

def load_employees():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Employee(**emp) for emp in data]

def save_employees(employees):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([emp.__dict__ for emp in employees], f, ensure_ascii=False, indent=2)

def load_schedules():
    if not os.path.exists(SCHEDULE_FILE):
        return {}
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {date: DailySchedule.from_dict(val) for date, val in data.items()}

def save_schedules(schedules):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump({date: sch.to_dict() for date, sch in schedules.items()}, f, ensure_ascii=False, indent=2)
