# models/employee.py
class Employee:
    def __init__(self, id, name, role, skill_level, home_branch,
                 fixed_holidays=None, holiday_requests=None,
                 min_shifts_per_week=0, max_shifts_per_week=6):
        self.id = id
        self.name = name
        self.role = role                  # 사장 / 매니저 / 직원
        self.skill_level = skill_level    # C / N
        self.home_branch = home_branch    # A / B
        self.fixed_holidays = fixed_holidays or []   # [0, 2] 형태
        self.holiday_requests = holiday_requests or []  # ['2025-08-12', ...]
        self.min_shifts_per_week = min_shifts_per_week  # 최소 근무 횟수
        self.max_shifts_per_week = max_shifts_per_week  # 최대 근무 횟수
