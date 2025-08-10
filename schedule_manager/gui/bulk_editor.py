# gui/bulk_editor.py
import calendar
from datetime import date, datetime, timedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QLineEdit, QCheckBox,
    QRadioButton, QPushButton, QMessageBox, QButtonGroup
)
from PySide6.QtCore import QDate
from schedule_manager.models.schedule import DailySchedule

class BulkEditorDialog(QDialog):
    """
    기간(시작~종료) 지정 후 일괄 작업:
      - 삭제
      - 내용 비우기(근무/휴무/메모 초기화, 휴업 해제)
      - 휴업 설정
      - 휴업 해제
      - 메모 일괄 설정(선택)
    """
    def __init__(self, parent, year: int, month: int, schedules: dict):
        super().__init__(parent)
        self.setWindowTitle("일정 일괄 편집")
        self.schedules = schedules
        self.changed = False

        v = QVBoxLayout(self)

        # 기간 선택: 기본은 현재 보이는 달 전체
        first_day = QDate(year, month, 1)
        last_day = QDate(year, month, calendar.monthrange(year, month)[1])

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("시작일"))
        self.start_edit = QDateEdit(first_day); self.start_edit.setCalendarPopup(True)
        row1.addWidget(self.start_edit)
        row1.addSpacing(12)
        row1.addWidget(QLabel("종료일"))
        self.end_edit = QDateEdit(last_day); self.end_edit.setCalendarPopup(True)
        row1.addWidget(self.end_edit)
        v.addLayout(row1)

        # 프리셋: 주간(선택일 기준 일~토), 월 전체
        row2 = QHBoxLayout()
        btn_week = QPushButton("이번 주(일~토)로 설정")
        btn_week.clicked.connect(self.set_week_range)
        btn_month = QPushButton("이번 달 전체")
        btn_month.clicked.connect(lambda: self.set_month_range(year, month))
        row2.addWidget(btn_week); row2.addWidget(btn_month)
        v.addLayout(row2)

        # 작업 선택
        v.addWidget(QLabel("작업 선택"))
        self.grp = QButtonGroup(self)
        self.rb_delete = QRadioButton("삭제(해당 기간의 일정 키 제거)")
        self.rb_clear  = QRadioButton("내용 비우기(근무/휴무/메모 초기화, 휴업 해제)")
        self.rb_close  = QRadioButton("휴업 설정")
        self.rb_open   = QRadioButton("휴업 해제")
        self.rb_clear.setChecked(True)
        for rb in (self.rb_delete, self.rb_clear, self.rb_close, self.rb_open):
            self.grp.addButton(rb)
            v.addWidget(rb)

        # 메모 일괄 설정(선택)
        self.memo_input = QLineEdit()
        self.memo_input.setPlaceholderText("선택 입력: 모든 날짜에 동일 메모 설정")
        v.addWidget(self.memo_input)

        # 하단 버튼
        row3 = QHBoxLayout()
        row3.addStretch(1)
        btn_apply = QPushButton("적용")
        btn_cancel = QPushButton("취소")
        row3.addWidget(btn_cancel); row3.addWidget(btn_apply)
        v.addLayout(row3)

        btn_cancel.clicked.connect(self.reject)
        btn_apply.clicked.connect(self.on_apply)

    # --------- helpers ----------
    def qd_to_py(self, qd: QDate) -> date:
        return date(qd.year(), qd.month(), qd.day())

    def iter_range(self, start: date, end: date):
        d = start
        while d <= end:
            yield d
            d = d + timedelta(days=1)

    def set_week_range(self):
        # start_edit의 주(일~토)로 잡기
        base = self.qd_to_py(self.start_edit.date())
        # 일요일이 6 in Python? weekday(): 0=월..6=일 → 일요일로 내리기
        delta_to_sun = (base.weekday() + 1) % 7  # 월0..일6 → 일까지 일수
        sunday = base - timedelta(days=delta_to_sun)
        saturday = sunday + timedelta(days=6)
        self.start_edit.setDate(QDate(sunday.year, sunday.month, sunday.day))
        self.end_edit.setDate(QDate(saturday.year, saturday.month, saturday.day))

    def set_month_range(self, year: int, month: int):
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        self.start_edit.setDate(QDate(first.year, first.month, first.day))
        self.end_edit.setDate(QDate(last.year, last.month, last.day))

    # --------- apply ----------
    def on_apply(self):
        sd = self.qd_to_py(self.start_edit.date())
        ed = self.qd_to_py(self.end_edit.date())
        if sd > ed:
            QMessageBox.warning(self, "확인", "시작일이 종료일보다 이후입니다.")
            return

        memo = self.memo_input.text().strip()
        do_delete = self.rb_delete.isChecked()
        do_clear = self.rb_clear.isChecked()
        do_close = self.rb_close.isChecked()
        do_open  = self.rb_open.isChecked()

        count = 0
        for d in self.iter_range(sd, ed):
            key = d.strftime("%Y-%m-%d")
            if do_delete:
                if key in self.schedules:
                    self.schedules.pop(key, None)
                    count += 1
                continue

            sch = self.schedules.get(key) or DailySchedule(key)
            if do_clear:
                sch.working["OS"] = []
                sch.working["HC"] = []
                sch.holidays = []
                sch.memo = ""
                sch.closed = False
            if do_close:
                sch.closed = True
            if do_open:
                sch.closed = False
            if memo:
                sch.memo = memo

            self.schedules[key] = sch
            count += 1

        self.changed = True
        QMessageBox.information(self, "완료", f"{count}건 처리되었습니다.")
        self.accept()
