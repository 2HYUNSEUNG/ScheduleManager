# data/models.py
from dataclasses import dataclass
from typing import Optional, Literal

ShiftType = Literal["근무", "휴무"]

@dataclass(frozen=True)
class Employee:
    id: int
    name: str
    store_pref: Optional[str] = None          # 선호 지점 (없으면 None)
    fixed_off: Optional[str] = None           # "Mon,Wed" 같은 CSV (간단화)
    notes: Optional[str] = None

@dataclass
class Shift:
    id: Optional[int]
    date: str                                  # "YYYY-MM-DD"
    store_id: Optional[str]                    # "OS" | "HC" | None (휴무면 None)
    employee_id: int
    type: ShiftType                            # "근무" | "휴무"
    memo: Optional[str] = None
