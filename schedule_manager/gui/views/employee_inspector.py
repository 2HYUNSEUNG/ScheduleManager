# schedule_manager/gui/views/employee_inspector.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
import calendar

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QDate
from PySide6.QtGui import QAction, QColor, QBrush
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QTableView, QHeaderView,
    QLabel, QPushButton, QMenu
)

from schedule_manager.data.data_manager import (
    load_employees, load_schedules, save_schedules
)

BRANCHES = ("OS", "HC")
WEEKDAYS_KR = ["일", "월", "화", "수", "목", "금", "토"]

# ---- helpers: 스케줄 접근/수정 ----
def _ensure_day(schedules: Dict, key: str):
    if key not in schedules or schedules[key] is None:
        class _Sch:
            def __init__(self, date_key: str):
                self.date: str = date_key
                self.working: Dict[str, List[int]] = {"OS": [], "HC": []}
                self.holidays: List[int] = []
                self.memo: str = ""
                self.closed: bool = False          # ← 추가

            def to_dict(self) -> Dict:
                return {
                    "date": self.date,
                    "working": self.working,
                    "holidays": self.holidays,
                    "memo": self.memo,
                    "closed": self.closed,          # ← 추가
                }
        schedules[key] = _Sch(key)
        return schedules[key]

    # 기존 값 보정
    sch = schedules[key]
    if isinstance(sch, dict):
        sch.setdefault("date", key)
        sch.setdefault("working", {"OS": [], "HC": []})
        sch["working"].setdefault("OS", [])
        sch["working"].setdefault("HC", [])
        sch.setdefault("holidays", [])
        sch.setdefault("memo", "")
        sch.setdefault("closed", False)            # ← 추가
    else:
        if not hasattr(sch, "date"): setattr(sch, "date", key)
        if not hasattr(sch, "working") or sch.working is None:
            setattr(sch, "working", {"OS": [], "HC": []})
        else:
            sch.working.setdefault("OS", [])
            sch.working.setdefault("HC", [])
        if not hasattr(sch, "holidays") or sch.holidays is None:
            setattr(sch, "holidays", [])
        if not hasattr(sch, "memo"): setattr(sch, "memo", "")
        if not hasattr(sch, "closed"): setattr(sch, "closed", False)  # ← 추가
    return sch

def get_emp_status(schedules: Dict, y: int, m: int, d: int, emp_id: int) -> Optional[str]:
    key = f"{y:04d}-{m:02d}-{d:02d}"
    sch = schedules.get(key)
    if not sch:
        return None

    # dict/객체 모두 대응
    holidays = getattr(sch, "holidays", None)
    if holidays is None and isinstance(sch, dict):
        holidays = sch.get("holidays", [])
    holidays = holidays or []

    if emp_id in holidays:
        return "OFF"

    working = getattr(sch, "working", None)
    if working is None and isinstance(sch, dict):
        working = sch.get("working", {})
    working = working or {}

    for b in ("OS", "HC"):
        ids = working.get(b, []) if isinstance(working, dict) else getattr(working, b, [])
        if emp_id in (ids or []):
            return b
    return None


def set_emp_status(schedules: Dict, y: int, m: int, d: int, emp_id: int, status: Optional[str]):
    """
    status: 'OS'|'HC'|'OFF'|None
    - None: 해당 일자에서 완전 제거
    """
    key = f"{y:04d}-{m:02d}-{d:02d}"
    sch = _ensure_day(schedules, key)

    # 제거부터
    for b in BRANCHES:
        if emp_id in sch.working.get(b, []):
            sch.working[b] = [x for x in sch.working[b] if x != emp_id]
    if emp_id in (sch.holidays or []):
        sch.holidays = [x for x in sch.holidays if x != emp_id]

    # 새 상태 반영
    if status == "OFF":
        sch.holidays = (sch.holidays or []) + [emp_id]
    elif status in BRANCHES:
        sch.working[status] = (sch.working.get(status) or []) + [emp_id]
    else:
        # None: do nothing (완전 제거된 상태 유지)
        pass

# ---- 테이블 모델 (달력 그리드) ----
class EmployeeMonthModel(QAbstractTableModel):
    def __init__(self, schedules: Dict, year: int, month: int, emp_id: int, parent=None):
        super().__init__(parent)
        self.schedules = schedules
        self.year = year
        self.month = month
        self.emp_id = emp_id
        self._rebuild_grid()

    # 달력 그리드 구성 (주차 x 요일)
    def _rebuild_grid(self):
        first = QDate(self.year, self.month, 1)
        days = first.daysInMonth()
        # QDate.dayOfWeek(): Mon=1 .. Sun=7 → 일=0, 월=1 ... 토=6
        first_wd_qt = first.dayOfWeek()
        first_wd = 0 if first_wd_qt == 7 else first_wd_qt

        total_cells = first_wd + days
        rows = (total_cells + 6) // 7  # 올림
        self.grid = [[None for _ in range(7)] for _ in range(rows)]
        day = 1
        for i in range(rows):
            for j in range(7):
                idx = i * 7 + j
                if idx >= first_wd and day <= days:
                    self.grid[i][j] = day
                    day += 1

    # Qt 모델 필수 구현
    def rowCount(self, _=QModelIndex()):
        return len(self.grid)

    def columnCount(self, _=QModelIndex()):
        return 7

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return WEEKDAYS_KR[section]
        return f"{section + 1}주"

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable  # 편집 불가

    def data(self, index, role):
        if not index.isValid():
            return None
        day = self.grid[index.row()][index.column()]

        if day is None:
            if role == Qt.DisplayRole:
                return ""
            if role == Qt.BackgroundRole:
                return QBrush(QColor("#f5f5f7"))
            if role == Qt.ForegroundRole:
                return QBrush(QColor("#1f2937"))
            return None

        status = get_emp_status(self.schedules, self.year, self.month, day, self.emp_id)

        if role == Qt.DisplayRole:
            label = "—" if status is None else ("휴무" if status == "OFF" else status)
            return f"{day}\n{label}"

        if role == Qt.TextAlignmentRole:
            return Qt.AlignHCenter | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            return QBrush(QColor("#111827"))  # 모든 요일 동일 글씨색

        if role == Qt.BackgroundRole:
            if status is None:
                return QBrush(QColor("#ffe0e0"))  # 미배정
            if status == "OFF":
                return QBrush(QColor("#e9ecef"))  # 휴무
            return QBrush(QColor("#cfe8ff" if status == "OS" else "#cfeee0"))

        if role == Qt.ToolTipRole:
            ymd = f"{self.year}-{self.month:02d}-{day:02d}"
            if status is None:
                return f"{ymd} 미배정"
            if status == "OFF":
                return f"{ymd} 휴무"
            return f"{ymd} 근무({status})"

        return None

    # 유틸
    def refresh(self):
        self.beginResetModel()
        self._rebuild_grid()
        self.endResetModel()

    def day_at(self, row: int, col: int):
        return self.grid[row][col]

# ---- 다이얼로그 ----
class EmployeeInspectorDialog(QDialog):
    """
    직원 목록(좌) + 직원별 월 달력(우)
    더블클릭: 휴무 <-> 근무(OS) 토글
    우클릭: OS/HC/휴무/제거 메뉴
    """
    def __init__(self, year: int, month: int, parent=None, on_changed: Optional[Callable] = None):
        super().__init__(parent)
        self.setWindowTitle("직원별 근무/휴무")
        self.resize(1100, 540)

        self.year = year
        self.month = month
        self.on_changed = on_changed

        self.employees = load_employees()
        self.schedules = load_schedules()
        self.current_emp_id: Optional[int] = None

        # 상단 바(월 이동)
        top = QHBoxLayout()
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        self.lbl_month = QLabel()
        top.addWidget(self.btn_prev)
        top.addWidget(self.lbl_month)
        top.addWidget(self.btn_next)
        top.addStretch(1)

        # 좌: 직원 리스트
        self.list = QListWidget()
        for e in self.employees:
            self.list.addItem(f"{e.id}: {e.name}")

        # 우: 테이블
        self.table = QTableView()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._ctx_menu)
        self.table.doubleClicked.connect(self._on_double)

        # 가독성/동작 옵션 (뷰에만 둔다)
        self.table.setWordWrap(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setDefaultSectionSize(56)    # 두 줄 보기 좋게
        self.table.horizontalHeader().setDefaultSectionSize(96)   # 칸 너비
        self.table.setStyleSheet("""
        QTableView { font-size: 12px; }
        QHeaderView::section { font-weight: 600; }
        """)

        # 레이아웃
        root = QVBoxLayout(self)
        root.addLayout(top)
        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addWidget(self.table, 4)
        root.addLayout(body)

        # 시그널
        self.btn_prev.clicked.connect(self._prev_month)
        self.btn_next.clicked.connect(self._next_month)
        self.list.currentRowChanged.connect(self._on_select)

        # 초기 상태
        self._update_month_label()
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    # 내부
    def _update_month_label(self):
        days = calendar.monthrange(self.year, self.month)[1]
        self.lbl_month.setText(f"{self.year}-{self.month:02d}  (일수 {days}일)")

    def _load_model(self):
        if self.current_emp_id is None:
            self.table.setModel(None)
            return
        self.model = EmployeeMonthModel(self.schedules, self.year, self.month, self.current_emp_id, self)
        self.table.setModel(self.model)

    # slots
    def _on_select(self, _row: int):
        if _row < 0 or _row >= len(self.employees):
            self.current_emp_id = None
            self.table.setModel(None)
            return
        self.current_emp_id = self.employees[_row].id
        self._load_model()

    def _prev_month(self):
        if self.month == 1:
            self.year -= 1
            self.month = 12
        else:
            self.month -= 1
        self._update_month_label()
        if getattr(self, "model", None):
            self.model.year, self.model.month = self.year, self.month
            self.model.refresh()

    def _next_month(self):
        if self.month == 12:
            self.year += 1
            self.month = 1
        else:
            self.month += 1
        self._update_month_label()
        if getattr(self, "model", None):
            self.model.year, self.model.month = self.year, self.month
            self.model.refresh()

    def _on_double(self, index: QModelIndex):
        if not index.isValid() or self.current_emp_id is None:
            return
        day = self.model.day_at(index.row(), index.column())
        if day is None:
            return

        cur = get_emp_status(self.schedules, self.year, self.month, day, self.current_emp_id)
        nxt = self._next_status(cur)

        # nxt == None 이면 미배정(완전 제거)
        set_emp_status(self.schedules, self.year, self.month, day, self.current_emp_id, nxt)

        save_schedules(self.schedules)
        self.model.refresh()
        if self.on_changed:
            self.on_changed()

    def _ctx_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid() or self.current_emp_id is None:
            return
        day = self.model.day_at(index.row(), index.column())
        if day is None:
            return

        menu = QMenu(self)
        a_os = QAction("지점 OS로 배정", self)
        a_hc = QAction("지점 HC로 배정", self)
        a_off = QAction("휴무로 설정", self)
        a_clear = QAction("배정 제거", self)
        menu.addAction(a_os)
        menu.addAction(a_hc)
        menu.addSeparator()
        menu.addAction(a_off)
        menu.addSeparator()
        menu.addAction(a_clear)

        act = menu.exec(self.table.viewport().mapToGlobal(pos))
        if act is None:
            return

        if act == a_os:
            set_emp_status(self.schedules, self.year, self.month, day, self.current_emp_id, "OS")
        elif act == a_hc:
            set_emp_status(self.schedules, self.year, self.month, day, self.current_emp_id, "HC")
        elif act == a_off:
            set_emp_status(self.schedules, self.year, self.month, day, self.current_emp_id, "OFF")
        elif act == a_clear:
            set_emp_status(self.schedules, self.year, self.month, day, self.current_emp_id, None)

        save_schedules(self.schedules)
        self.model.refresh()
        if self.on_changed:
            self.on_changed()

    def _next_status(self, cur: Optional[str]) -> Optional[str]:
        order = ["OS", "HC", "OFF", None]  # 표시상: OS, HC, 휴무, 미배정
        try:
            i = order.index(cur)
            return order[(i + 1) % len(order)]
        except ValueError:
            # 혹시 예상 밖 값이면 OS부터 시작
            return "OS"

