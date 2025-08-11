# gui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QToolBar, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QSizePolicy, QMessageBox,
    QLineEdit, QComboBox, QGroupBox, QGridLayout, QHeaderView, QAbstractItemView,
    QSplitter, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from datetime import date
import calendar

from schedule_manager.data.data_manager import (
    load_employees, load_schedules, save_schedules, save_employees,
    load_notes, save_notes
)
from schedule_manager.logic.scheduler import auto_assign
from schedule_manager.gui.calendar_widget import CalendarWidget
from schedule_manager.gui.day_editor import open_day_editor
from schedule_manager.gui.bulk_editor import BulkEditorDialog

ROLE_OPTIONS = ["사장", "매니저", "직원"]
BRANCH_OPTIONS = ["OS", "HC"]                # 지점 코드
SKILL_OPTIONS = [("○", "C"), ("X", "N")]     # (표시, 저장값)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("근무/휴무 스케줄러")
        self.resize(1280, 950)

        today = date.today()
        self.year = today.year
        self.month = today.month

        self.employees = load_employees()
        self.schedules = load_schedules()
        self._editing_emp_id = None  # 현재 편집 중인 직원 ID

        self._build_ui()
        self.refresh()

    # ---------------- UI ----------------
    def _build_ui(self):
        # Toolbar
        tb = QToolBar()
        self.addToolBar(tb)

        btn_prev = QPushButton("◀ 이전달")
        btn_prev.clicked.connect(self.prev_month)
        tb.addWidget(btn_prev)

        self.month_label = QLabel("")
        self.month_label.setStyleSheet("font-weight:600; padding:0 8px;")
        tb.addWidget(self.month_label)

        btn_next = QPushButton("다음달 ▶")
        btn_next.clicked.connect(self.next_month)
        tb.addWidget(btn_next)

        tb.addSeparator()

        btn_auto = QPushButton("현재 달 자동 배정")
        btn_auto.setToolTip("보이는 달의 1일부터 말일까지 자동 배정")
        btn_auto.clicked.connect(self.run_auto_assign_current_month)
        tb.addWidget(btn_auto)

        btn_refresh = QPushButton("새로고침")
        btn_refresh.clicked.connect(self.refresh)
        tb.addWidget(btn_refresh)

        btn_bulk = QPushButton("일정 일괄 편집")
        btn_bulk.clicked.connect(self.open_bulk_editor)
        tb.addWidget(btn_bulk)

        # 툴바: 좌측 패널 토글
        self.act_toggle_left = QAction("관리 패널 보기", self)
        self.act_toggle_left.setCheckable(True)
        self.act_toggle_left.setChecked(True)
        self.act_toggle_left.toggled.connect(self.toggle_left_panel)
        tb.addAction(self.act_toggle_left)

        # 중앙: 스플리터
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)
        # 여백 제거 → 캘린더가 패널에 '딱' 붙게
        root.setContentsMargins(0, 0, 0, 0)
        splitter.setHandleWidth(2)  # 핸들 얇게

        # ----- 좌측 컨테이너 -----
        left_container = QWidget()
        left = QVBoxLayout(left_container)

        # (A) 직원 편집 바
        self.edit_box = QGroupBox("직원 추가/편집")
        form = QGridLayout(self.edit_box)
        r = 0

        self.emp_id = QLineEdit()
        self.emp_id.setReadOnly(True)
        self.emp_id.setPlaceholderText("ID는 자동 부여됩니다.")
        form.addWidget(QLabel("ID"), r, 0); form.addWidget(self.emp_id, r, 1); r += 1

        self.emp_name = QLineEdit()
        form.addWidget(QLabel("이름*"), r, 0); form.addWidget(self.emp_name, r, 1); r += 1

        self.emp_role = QComboBox(); self.emp_role.addItems(ROLE_OPTIONS)
        form.addWidget(QLabel("직급"), r, 0); form.addWidget(self.emp_role, r, 1); r += 1

        self.emp_skill = QComboBox()
        for disp, val in SKILL_OPTIONS:
            self.emp_skill.addItem(disp, userData=val)
        form.addWidget(QLabel("조리"), r, 0); form.addWidget(self.emp_skill, r, 1); r += 1

        self.emp_branch = QComboBox(); self.emp_branch.addItems(BRANCH_OPTIONS)
        form.addWidget(QLabel("지점"), r, 0); form.addWidget(self.emp_branch, r, 1); r += 1

        # 버튼
        btn_bar = QHBoxLayout()
        self.btn_new_emp = QPushButton("초기화")
        self.btn_save_emp = QPushButton("저장")
        self.btn_del_emp = QPushButton("직원 삭제")
        btn_bar.addWidget(self.btn_new_emp)
        btn_bar.addWidget(self.btn_save_emp)
        btn_bar.addWidget(self.btn_del_emp)
        form.addLayout(btn_bar, r, 1)

        left.addWidget(self.edit_box)

        # (B) 직원 목록
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("직원 목록"))
        title_row.addStretch(1)
        left.addLayout(title_row)

        self.emp_table = QTableWidget(0, 4)
        self.emp_table.setEditTriggers(QAbstractItemView.NoEditTriggers)    # 셀 직접 편집 금지
        self.emp_table.setSelectionBehavior(QAbstractItemView.SelectRows)   # 행 단위 선택
        self.emp_table.setSelectionMode(QAbstractItemView.SingleSelection)  # 단일 행 선택
        self.emp_table.setHorizontalHeaderLabels(["이름", "직급", "조리", "지점"])
        self.emp_table.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        header = self.emp_table.horizontalHeader()
        header.setStretchLastSection(False)
        for i in range(self.emp_table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.Fixed)
            self.emp_table.setColumnWidth(i, 65)

        left.addWidget(self.emp_table)

        # 노트 박스
        self.notes_box = QGroupBox("노트")
        nb = QVBoxLayout(self.notes_box)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("공지, 특이사항, 휴무신청 등")
        self.notes_edit.setMinimumHeight(140)  # 보기 편하게 약간 높이 확보
        self.notes_edit.setAcceptRichText(False)  # 순수 텍스트
        nb.addWidget(self.notes_edit)

        btn_row = QHBoxLayout()
        self.btn_notes_save = QPushButton("저장")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_notes_save)
        nb.addLayout(btn_row)

        left.addWidget(self.notes_box)
        # ▲▲▲ 노트 박스 추가 끝 ▲▲▲

        self.notes_edit.setPlainText(load_notes())

        # 좌측 폭 정책: 최소만 보장, 최대는 제한해서 달력 넓게
        left_container.setMinimumWidth(300)   # 편집폼+표가 무너지지 않을 최소폭
        left_container.setMaximumWidth(300)   # 너무 넓어지지 않도록 상한

        # ----- 우측 컨테이너 -----
        right_container = QWidget()
        right = QVBoxLayout(right_container)
        self.calendar = CalendarWidget(on_day_open=self.open_day, on_day_delete=self.delete_day)
        right.addWidget(self.calendar)

        # 스플리터에 붙이기
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)  # left
        splitter.setStretchFactor(1, 1)  # right 크게
        splitter.setCollapsible(0, True) # 좌측 접기 가능
        splitter.setCollapsible(1, False)
        self._splitter = splitter
        self._left_container = left_container

        left_min = left_container.minimumWidth()
        splitter.setSizes([left_min, 10_000])  # 오른쪽이 거의 전부 차지
        self._left_last_width = left_min  # 이후 토글 복원도 최소폭

        # 시그널
        self.emp_table.itemSelectionChanged.connect(self._on_emp_selected)
        self.emp_table.cellDoubleClicked.connect(self._on_emp_double)
        self.btn_new_emp.clicked.connect(self._clear_emp_form)
        self.btn_save_emp.clicked.connect(self._save_emp_form)
        self.btn_del_emp.clicked.connect(self._delete_selected_emp)
        self.btn_notes_save.clicked.connect(self._save_notes_ui)

        # 상태바
        self.status = self.statusBar()

    # ---------------- 데이터/바인딩 ----------------
    def _fill_emp_table(self):
        self.emp_table.setRowCount(0)
        for e in self.employees:
            r = self.emp_table.rowCount()
            self.emp_table.insertRow(r)
            skill = "○" if getattr(e, "skill_level", "") in ("C", "cook") else "X"
            self.emp_table.setItem(r, 0, QTableWidgetItem(e.name))
            self.emp_table.setItem(r, 1, QTableWidgetItem(e.role))
            self.emp_table.setItem(r, 2, QTableWidgetItem(skill))
            self.emp_table.setItem(r, 3, QTableWidgetItem(e.home_branch))
            # 행 히든 데이터로 ID 저장
            for c in range(4):
                self.emp_table.item(r, c).setData(Qt.UserRole, e.id)

    def _on_emp_selected(self):
        row = self.emp_table.currentRow()
        if row < 0:
            return
        item = self.emp_table.item(row, 0)
        emp_id = item.data(Qt.UserRole)
        self._bind_emp_form(emp_id)

    def _on_emp_double(self, row, _col):
        item = self.emp_table.item(row, 0)
        if not item:
            return
        self._bind_emp_form(item.data(Qt.UserRole))

    def _bind_emp_form(self, emp_id: int):
        e = next((x for x in self.employees if x.id == emp_id), None)
        if not e:
            return
        self._editing_emp_id = e.id
        self.emp_id.setText(str(e.id))
        self.emp_name.setText(e.name)
        self.emp_role.setCurrentIndex(ROLE_OPTIONS.index(e.role) if e.role in ROLE_OPTIONS else 0)
        # 숙련
        sk = getattr(e, "skill_level", "")
        idx = 0
        for i in range(self.emp_skill.count()):
            if self.emp_skill.itemData(i) in (sk, ("C" if sk == "cook" else sk)):
                idx = i
                break
        self.emp_skill.setCurrentIndex(idx)
        # 지점
        self.emp_branch.setCurrentIndex(BRANCH_OPTIONS.index(e.home_branch) if e.home_branch in BRANCH_OPTIONS else 0)

    def _clear_emp_form(self):
        self._editing_emp_id = None
        self.emp_id.clear()
        self.emp_name.clear()
        self.emp_role.setCurrentIndex(0)
        self.emp_skill.setCurrentIndex(0)
        self.emp_branch.setCurrentIndex(0)
        self.emp_table.clearSelection()

    def _collect_emp_form(self):
        name = self.emp_name.text().strip()
        role = self.emp_role.currentText()
        skill_val = self.emp_skill.currentData()  # "C"/"N"
        branch = self.emp_branch.currentText()
        return name, role, skill_val, branch

    def _save_emp_form(self):
        name, role, skill_val, branch = self._collect_emp_form()
        if not name:
            QMessageBox.warning(self, "확인", "이름을 입력해주세요.")
            self.emp_name.setFocus()
            return

        if self._editing_emp_id is None:
            # 신규: 내부 기본값 포함(비공개 필드)
            new_id = (max([e.id for e in self.employees], default=0) + 1)
            self.employees.append(self._mk_emp(
                id=new_id, name=name, role=role, skill_level=skill_val,
                home_branch=branch,
                fixed_holidays=[],     # 기본값
                min_shifts_per_week=0, # 기본값
                max_shifts_per_week=6  # 기본값
            ))
            msg = "추가 완료."
        else:
            # 수정
            e = next((x for x in self.employees if x.id == self._editing_emp_id), None)
            if not e:
                QMessageBox.warning(self, "오류", "편집 대상 직원을 찾지 못했습니다.")
                return
            e.name = name
            e.role = role
            e.skill_level = skill_val
            e.home_branch = branch
            msg = "수정 완료."

        save_employees(self.employees)
        self.refresh()
        QMessageBox.information(self, "완료", msg)

    def _delete_selected_emp(self):
        row = self.emp_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "안내", "삭제할 직원을 선택해주세요.")
            return

        emp_id = self.emp_table.item(row, 0).data(Qt.UserRole)
        name = self.emp_table.item(row, 0).text()

        if QMessageBox.question(self, "확인", f"[{name}]을(를) 삭제하시겠습니까?") != QMessageBox.Yes:
            return

        # 1) 직원 목록에서 제거
        self.employees = [e for e in self.employees if e.id != emp_id]
        save_employees(self.employees)

        # 2) 모든 스케줄에서 해당 ID 제거 (OS/HC/휴무)
        changed = False
        for key, sch in list(self.schedules.items()):
            os = sch.working.get("OS", []) or []
            hc = sch.working.get("HC", []) or []
            nos = [i for i in os if i != emp_id]
            nhc = [i for i in hc if i != emp_id]
            h = sch.holidays or []
            nh = [i for i in h if i != emp_id]

            if nos != os or nhc != hc or nh != h:
                sch.working["OS"] = nos
                sch.working["HC"] = nhc
                sch.holidays = nh
                self.schedules[key] = sch
                changed = True

        if changed:
            save_schedules(self.schedules)

        self._clear_emp_form()
        self.refresh()
        QMessageBox.information(self, "완료", f"[{name}] 삭제 및 과거 스케줄 정리 완료.")

    # ---------------- 동작 ----------------
    def refresh(self):
        self.employees = load_employees()
        self.schedules = load_schedules()
        self._fill_emp_table()
        self.calendar.render_month(self.year, self.month, self.employees, self.schedules)

        # 상단 상태
        month_days = calendar.monthrange(self.year, self.month)[1]
        self.month_label.setText(f"{self.year}-{self.month:02d}  (일수: {month_days}일)")
        self.statusBar().showMessage(f"직원 {len(self.employees)}명, 일정 {len(self.schedules)}건")

    def open_day(self, y: int, m: int, d: int):
        key = f"{y:04d}-{m:02d}-{d:02d}"
        changed = open_day_editor(self, key, self.employees, self.schedules)
        if changed:
            save_schedules(self.schedules)
            self.refresh()

    def run_auto_assign_current_month(self):
        month_days = calendar.monthrange(self.year, self.month)[1]
        start = f"{self.year:04d}-{self.month:02d}-01"
        msg = (
            f"{self.year}-{self.month:02d} ({month_days}일)\n\n"
            "이 달의 자동 배정을 실행할까요?\n"
            "※ 기존 배정은 유지되고 빈 칸만 채워집니다."
        )

        # 확인 대화상자 (버튼 라벨: 예 / 아니오)
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Question)
        mb.setWindowTitle("자동 배정 확인")
        mb.setText(msg)
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mb.setDefaultButton(QMessageBox.No)  # 기본: 아니오
        mb.button(QMessageBox.Yes).setText("예")
        mb.button(QMessageBox.No).setText("아니오")

        ret = mb.exec()
        if ret != QMessageBox.Yes:
            self.status.showMessage("자동 배정을 취소했습니다.", 3000)
            return

        # 실행
        auto_assign(start_date=start, days=month_days, overwrite=False)
        self.refresh()
        QMessageBox.information(self, "완료", f"{self.year}-{self.month:02d} 자동 배정을 완료했습니다.")

    def prev_month(self):
        if self.month == 1:
            self.year -= 1
            self.month = 12
        else:
            self.month -= 1
        self.refresh()

    def next_month(self):
        if self.month == 12:
            self.year += 1
            self.month = 1
        else:
            self.month += 1
        self.refresh()

    def delete_day(self, date_key: str):
        if date_key in self.schedules:
            if QMessageBox.question(self, "확인", f"{date_key} 일정을 삭제하시겠습니까?") != QMessageBox.Yes:
                return
            self.schedules.pop(date_key, None)
            save_schedules(self.schedules)
            self.refresh()
            QMessageBox.information(self, "삭제", f"{date_key} 삭제 완료.")
        else:
            QMessageBox.information(self, "안내", "삭제할 일정이 없습니다.")

    def open_bulk_editor(self):
        dlg = BulkEditorDialog(self, self.year, self.month, self.schedules)
        if dlg.exec():
            if dlg.changed:
                save_schedules(self.schedules)
                self.refresh()

    # ---------------- 노트 I/O ----------------
    def _save_notes_ui(self):
        save_notes(self.notes_edit.toPlainText())
        self.status.showMessage("노트 저장 완료.", 2000)

    # 간단 Employee 객체 생성 헬퍼(모델 클래스로 대체 가능)
    def _mk_emp(self, **kwargs):
        class _E:
            def __init__(self, **kw): self.__dict__.update(kw)
        return _E(**kwargs)

    def toggle_left_panel(self, visible: bool):
        sizes = self._splitter.sizes()
        if visible:
            left_min = self._left_container.minimumWidth()
            total = sum(sizes) if sizes else 1280
            self._left_container.setVisible(True)
            self._splitter.setSizes([left_min, max(total - left_min, 500)])
            self._left_last_width = left_min
        else:
            self._left_last_width = self._splitter.sizes()[0] if sizes and sizes[
                0] > 0 else self._left_container.minimumWidth()
            self._left_container.setVisible(False)
            self._splitter.setSizes([0, sum(sizes) if sizes else 1000])

