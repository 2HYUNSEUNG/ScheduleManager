# schedule_manager/gui/views/attendance_dialog.py
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDateEdit,
    QTableWidget, QTableWidgetItem, QMessageBox, QFormLayout, QDialogButtonBox,
    QLineEdit, QWidget, QAbstractItemView, QHeaderView, QSizePolicy
)

from schedule_manager.data.data_manager import (
    load_employees, load_schedules,
    load_attendance, punch_in, punch_out, adjust_attendance
)

BRANCHES = ("OS", "HC")

def _date_key(qd: QDate) -> str:
    return f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"

def _get_status_for(emp_id: int, date_key: str) -> str:
    """스케줄 기준 상태 텍스트(OS/HC/휴무/—)"""
    schedules = load_schedules()
    sch = schedules.get(date_key)
    if not sch:
        return "—"
    holidays = getattr(sch, "holidays", []) or []
    if emp_id in holidays:
        return "휴무"
    working = getattr(sch, "working", {}) or {}
    for b in BRANCHES:
        ids = working.get(b, []) if isinstance(working, dict) else []
        if emp_id in (ids or []):
            return b
    return "—"

class AdjustDialog(QDialog):
    def __init__(self, parent: QWidget, name: str, in_time: str, out_time: str):
        super().__init__(parent)
        self.setWindowTitle(f"근태 조정 - {name}")
        self._in = QLineEdit(in_time)
        self._out = QLineEdit(out_time)
        self._in.setPlaceholderText("예: 09:00 (비우면 초기화)")
        self._out.setPlaceholderText("예: 18:00 (비우면 초기화)")

        form = QFormLayout()
        form.addRow("출근", self._in)
        form.addRow("퇴근", self._out)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(btns)

    def values(self):
        return self._in.text().strip(), self._out.text().strip()

class AttendanceDialog(QDialog):
    """
    가운데 표에서 직원 선택 → 출근/퇴근/조정
    표 컬럼: 이름 / 출근 / 퇴근 / 상태 (모두 동일 폭)
    """
    def __init__(self, parent=None, date_qd: Optional[QDate] = None):
        super().__init__(parent)
        self.setWindowTitle("근태 기록")

        # 데이터
        self.employees = load_employees()
        self.date_edit = QDateEdit(date_qd or QDate.currentDate())
        self.date_edit.setCalendarPopup(True)

        # 상단 바
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        top.addWidget(QLabel("기록 일자"))
        top.addWidget(self.date_edit)
        top.addStretch(1)

        # 테이블 (단일 선택)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["이름", "출근", "퇴근", "상태"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)           # 행번호 숨김
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setTextElideMode(Qt.ElideRight)              # 긴 텍스트 …
        self.table.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        # 헤더: 4개 컬럼 모두 고정 폭으로
        hdr = self.table.horizontalHeader()
        for c in range(4):
            hdr.setSectionResizeMode(c, QHeaderView.Fixed)

        # 컴팩트하게
        self.table.setStyleSheet(
            "QTableView{font-size:12px;} QHeaderView::section{padding:2px 4px;}"
        )

        # 버튼들
        btn_in = QPushButton("출근")
        btn_out = QPushButton("퇴근")
        btn_adj = QPushButton("조정")
        btn_refresh = QPushButton("새로고침")

        btns_widget = QWidget()
        btns = QVBoxLayout(btns_widget)
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(6)
        btns.addWidget(btn_in)
        btns.addWidget(btn_out)
        btns.addWidget(btn_adj)
        btns.addStretch(1)
        btns.addWidget(btn_refresh)
        btns_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        # 레이아웃
        mid = QHBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(8)
        mid.addWidget(self.table)
        mid.addWidget(btns_widget, 0, Qt.AlignTop)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addLayout(top)
        root.addLayout(mid)

        # 시그널
        self.date_edit.dateChanged.connect(self.refresh)
        btn_in.clicked.connect(self.on_punch_in)
        btn_out.clicked.connect(self.on_punch_out)
        btn_adj.clicked.connect(self.on_adjust)
        btn_refresh.clicked.connect(self.refresh)

        # 초기 로딩
        self.refresh()

    # --- helpers ---
    def _selected_emp_id(self) -> Optional[int]:
        r = self.table.currentRow()
        if r < 0:
            return None
        return self.table.item(r, 0).data(Qt.UserRole)

    def _apply_column_widths(self):
        # 4개 컬럼 동일 고정 폭 (원하면 숫자만 바꿔도 됨)
        col_w = 92
        for c in range(4):
            self.table.setColumnWidth(c, col_w)

    # --- 동작 ---
    def refresh(self):
        day_key = _date_key(self.date_edit.date())
        att = load_attendance().get(day_key, {})
        self.table.setRowCount(0)

        for e in self.employees:
            rec = att.get(str(e.id), {})
            r = self.table.rowCount()
            self.table.insertRow(r)
            name_item = QTableWidgetItem(e.name)
            name_item.setData(Qt.UserRole, e.id)  # emp_id 저장
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, QTableWidgetItem(rec.get("in", "")))
            self.table.setItem(r, 2, QTableWidgetItem(rec.get("out", "")))
            self.table.setItem(r, 3, QTableWidgetItem(_get_status_for(e.id, day_key)))

        # 루프 끝난 뒤 한 번만 적용
        self._apply_column_widths()
        self._fit_table_width_to_contents()
        self._fit_table_height_to_contents()
        self._sync_dialog_width()

    def on_punch_in(self):
        emp_id = self._selected_emp_id()
        if not emp_id:
            QMessageBox.information(self, "안내", "출근할 직원을 선택해주세요.")
            return
        day_key = _date_key(self.date_edit.date())
        punch_in(day_key, emp_id)  # 최초만 기록
        self.refresh()

    def on_punch_out(self):
        emp_id = self._selected_emp_id()
        if not emp_id:
            QMessageBox.information(self, "안내", "퇴근할 직원을 선택해주세요.")
            return
        day_key = _date_key(self.date_edit.date())
        punch_out(day_key, emp_id)  # 최초만 기록
        self.refresh()

    def on_adjust(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, "안내", "조정할 직원을 선택해주세요.")
            return
        emp_id = self.table.item(r, 0).data(Qt.UserRole)
        name = self.table.item(r, 0).text()
        cur_in = self.table.item(r, 1).text()
        cur_out = self.table.item(r, 2).text()

        dlg = AdjustDialog(self, name, cur_in, cur_out)
        if dlg.exec() != QDialog.Accepted:
            return
        new_in, new_out = dlg.values()
        day_key = _date_key(self.date_edit.date())
        adjust_attendance(day_key, emp_id,
                          in_time=new_in if new_in != cur_in else new_in,
                          out_time=new_out if new_out != cur_out else new_out)
        self.refresh()

    # ---- 폭/높이 계산 & 다이얼로그 동기화 ----
    def _fit_table_width_to_contents(self):
        total_w = (self.table.frameWidth() * 2)
        if self.table.verticalHeader().isVisible():
            total_w += self.table.verticalHeader().width()
        for c in range(self.table.columnCount()):
            total_w += self.table.columnWidth(c)
        if self.table.verticalScrollBar().isVisible():
            total_w += self.table.verticalScrollBar().sizeHint().width()
        self.table.setFixedWidth(total_w)

    def _fit_table_height_to_contents(self):
        total_h = (self.table.frameWidth() * 2) + self.table.horizontalHeader().height()
        rows = self.table.rowCount()
        if rows == 0:
            total_h += self.table.verticalHeader().defaultSectionSize()
        else:
            for r in range(rows):
                total_h += self.table.rowHeight(r)
        if self.table.horizontalScrollBar().isVisible():
            total_h += self.table.horizontalScrollBar().sizeHint().height()
        self.table.setFixedHeight(total_h)

    def _compute_table_width(self) -> int:
        total = (self.table.frameWidth() * 2)
        if self.table.verticalHeader().isVisible():
            total += self.table.verticalHeader().width()
        for c in range(self.table.columnCount()):
            total += self.table.columnWidth(c)
        if self.table.verticalScrollBar().isVisible():
            total += self.table.verticalScrollBar().sizeHint().width()
        return total

    def _sync_dialog_width(self):
        table_w = self._compute_table_width()
        # 버튼 패널 폭
        btns_w = 0
        for w in self.findChildren(QWidget):
            if isinstance(w.layout(), QVBoxLayout) and any(
                isinstance(ch, QPushButton) for ch in w.findChildren(QPushButton)
            ):
                btns_w = w.sizeHint().width()
                break

        spacing = 8
        margins = 12 * 2
        target = table_w + spacing + btns_w + margins
        self.setMinimumWidth(target)
        self.resize(target, max(self.height(), self.minimumSizeHint().height()))
