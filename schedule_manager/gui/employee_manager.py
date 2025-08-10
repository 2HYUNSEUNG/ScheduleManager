# gui/employee_manager.py
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QCheckBox, QSpinBox,
    QSizePolicy, QGroupBox, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView
from schedule_manager.data.data_manager import load_employees, save_employees

ROLE_OPTIONS = ["사장", "매니저", "직원"]
BRANCH_OPTIONS = ["OS", "HC"]
SKILL_OPTIONS = [("○", "C"), ("X", "N")]   # (표시, 저장값)
WEEKDAYS = ["일", "화", "수", "목", "금", "토", "월"]  # Employee.fixed_holidays는 0=일 ~ 6=월

class EmployeeManagerDialog(QDialog):
    """
    직원 추가/수정/삭제 다이얼로그.
    좌측: 직원 테이블
    우측: 편집 패널(이름/직급/숙련/지점/고정휴무/주간최소·최대근무)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("직원 관리")
        self.resize(980, 620)

        self._employees = load_employees()
        self._editing_id = None
        self._build_ui()
        self._load_table()

        self.changed = False

    # ---------- UI ----------
    def _build_ui(self):
        root = QHBoxLayout(self)

        # 좌: 직원 표
        left = QVBoxLayout()
        left.addWidget(QLabel("직원 목록"))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "이름", "직급", "숙련", "지점", "고정휴무"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        left.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ 추가")
        self.btn_edit = QPushButton("✏ 수정")
        self.btn_del = QPushButton("🗑 삭제")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_del)
        left.addLayout(btn_row)

        # 우: 편집 패널
        right = QVBoxLayout()
        right.addWidget(QLabel("편집"))

        form = QGridLayout()
        r = 0

        form.addWidget(QLabel("ID"), r, 0)
        self.txt_id = QLineEdit()
        self.txt_id.setReadOnly(True)
        self.txt_id.setPlaceholderText("ID는 자동 부여됩니다.")
        form.addWidget(self.txt_id, r, 1)
        r += 1

        form.addWidget(QLabel("이름*"), r, 0)
        self.txt_name = QLineEdit()
        form.addWidget(self.txt_name, r, 1); r += 1

        form.addWidget(QLabel("직급"), r, 0)
        self.cmb_role = QComboBox(); self.cmb_role.addItems(ROLE_OPTIONS)
        form.addWidget(self.cmb_role, r, 1); r += 1

        form.addWidget(QLabel("숙련"), r, 0)
        self.cmb_skill = QComboBox()
        for disp, val in SKILL_OPTIONS:
            self.cmb_skill.addItem(disp, userData=val)
        form.addWidget(self.cmb_skill, r, 1); r += 1

        form.addWidget(QLabel("지점"), r, 0)
        self.cmb_branch = QComboBox(); self.cmb_branch.addItems(BRANCH_OPTIONS)
        form.addWidget(self.cmb_branch, r, 1); r += 1

        # 고정 휴무(체크박스 7개)
        gb = QGroupBox("고정 휴무(주)")
        daybox = QHBoxLayout()
        self.chk_days = []
        for i, name in enumerate(WEEKDAYS):
            cb = QCheckBox(name)
            cb.setProperty("weekday_index", i)  # 0=월..6=일
            self.chk_days.append(cb)
            daybox.addWidget(cb)
        gb.setLayout(daybox)
        right.addLayout(form)
        right.addWidget(gb)

        # 주간 근무 한도
        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel("주간 최소 근무"))
        self.spin_min = QSpinBox(); self.spin_min.setRange(0, 7); self.spin_min.setValue(0)
        limit_row.addWidget(self.spin_min)
        limit_row.addSpacing(12)
        limit_row.addWidget(QLabel("주간 최대 근무"))
        self.spin_max = QSpinBox(); self.spin_max.setRange(0, 7); self.spin_max.setValue(6)
        limit_row.addWidget(self.spin_max)
        right.addLayout(limit_row)

        # 저장/초기화/닫기
        action_row = QHBoxLayout()
        self.btn_new = QPushButton("초기화")
        self.btn_save = QPushButton("저장")
        self.btn_close = QPushButton("닫기")
        action_row.addWidget(self.btn_new)
        action_row.addWidget(self.btn_save)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_close)
        right.addLayout(action_row)

        # 레이아웃 합치기
        root.addLayout(left, 6)
        root.addLayout(right, 4)

        # 시그널
        self.table.cellDoubleClicked.connect(self._on_edit_from_table)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.btn_add.clicked.connect(self._on_new_clicked)
        self.btn_edit.clicked.connect(self._on_edit_clicked)
        self.btn_del.clicked.connect(self._on_delete_clicked)
        self.btn_new.clicked.connect(self._clear_form)
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_close.clicked.connect(self.accept)

    # ---------- 데이터 로드/표시 ----------
    def _load_table(self):
        self.table.setRowCount(0)
        for e in self._employees:
            r = self.table.rowCount()
            self.table.insertRow(r)
            fixed = ",".join(str(x) for x in (e.fixed_holidays or []))
            skill_label = "조리" if getattr(e, "skill_level", "") in ("C", "cook") else "비조리"
            self.table.setItem(r, 0, QTableWidgetItem(str(e.id)))
            self.table.setItem(r, 1, QTableWidgetItem(e.name))
            self.table.setItem(r, 2, QTableWidgetItem(e.role))
            self.table.setItem(r, 3, QTableWidgetItem(skill_label))
            self.table.setItem(r, 4, QTableWidgetItem(e.home_branch))
            self.table.setItem(r, 5, QTableWidgetItem(fixed))

        self.table.resizeColumnsToContents()

    def _on_selection_changed(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self._bind_form_from_row(row)

    def _bind_form_from_row(self, row: int):
        eid = int(self.table.item(row, 0).text())
        e = next((x for x in self._employees if x.id == eid), None)
        if not e:
            return
        self._editing_id = e.id
        self.txt_id.setText(str(e.id))
        self.txt_name.setText(e.name)
        self.cmb_role.setCurrentIndex(ROLE_OPTIONS.index(e.role) if e.role in ROLE_OPTIONS else 0)
        # 숙련
        sk = getattr(e, "skill_level", "")
        idx = 0
        for i in range(self.cmb_skill.count()):
            if self.cmb_skill.itemData(i) in (sk, ("C" if sk == "cook" else sk)):
                idx = i; break
        self.cmb_skill.setCurrentIndex(idx)
        # 지점
        self.cmb_branch.setCurrentIndex(BRANCH_OPTIONS.index(e.home_branch) if e.home_branch in BRANCH_OPTIONS else 0)
        # 고정휴무
        fixed = set(getattr(e, "fixed_holidays", []) or [])
        for cb in self.chk_days:
            cb.setChecked(cb.property("weekday_index") in fixed)
        # 주간 한도
        self.spin_min.setValue(getattr(e, "min_shifts_per_week", 0))
        self.spin_max.setValue(getattr(e, "max_shifts_per_week", 6))

    def _clear_form(self):
        self._editing_id = None
        self.txt_id.clear()
        self.txt_name.clear()
        self.cmb_role.setCurrentIndex(0)
        self.cmb_skill.setCurrentIndex(0)
        self.cmb_branch.setCurrentIndex(0)
        for cb in self.chk_days:
            cb.setChecked(False)
        self.spin_min.setValue(0)
        self.spin_max.setValue(6)
        self.table.clearSelection()

    # ---------- 버튼 동작 ----------
    def _on_new_clicked(self):
        self._clear_form()
        self.txt_name.setFocus()

    def _on_edit_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "안내", "수정할 직원을 선택해주세요.")
            return
        self._bind_form_from_row(row)

    def _on_edit_from_table(self, row, _col):
        self._bind_form_from_row(row)

    def _on_delete_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "안내", "삭제할 직원을 선택해주세요.")
            return
        eid = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        if QMessageBox.question(self, "확인", f"직원 [{name}]을(를) 삭제하시겠습니까?") != QMessageBox.Yes:
            return
        self._employees = [e for e in self._employees if e.id != eid]
        save_employees(self._employees)
        self._load_table()
        self._clear_form()
        self.changed = True

    def _on_save_clicked(self):
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "확인", "이름은 필수항목입니다.")
            self.txt_name.setFocus()
            return

        role = self.cmb_role.currentText()
        skill_val = self.cmb_skill.currentData()  # "C" or "N"
        branch = self.cmb_branch.currentText()
        fixed = [cb.property("weekday_index") for cb in self.chk_days if cb.isChecked()]
        min_w = int(self.spin_min.value())
        max_w = int(self.spin_max.value())
        if min_w > max_w:
            QMessageBox.warning(self, "확인", "주간 최소 근무가 최대 근무를 초과할 수 없습니다.")
            return

        # 새로 추가 or 수정
        if self._editing_id is None:
            new_id = (max([e.id for e in self._employees], default=0) + 1)
            emp = _mk_employee(
                id=new_id, name=name, role=role, skill_level=skill_val,
                home_branch=branch, fixed_holidays=fixed,
                min_shifts_per_week=min_w, max_shifts_per_week=max_w
            )
            self._employees.append(emp)
            msg = "추가 완료."
        else:
            emp = next((x for x in self._employees if x.id == self._editing_id), None)
            if not emp:
                QMessageBox.warning(self, "오류", "편집 대상 직원을 찾지 못했습니다.")
                return
            # 갱신
            emp.name = name
            emp.role = role
            emp.skill_level = skill_val
            emp.home_branch = branch
            emp.fixed_holidays = fixed
            emp.min_shifts_per_week = min_w
            emp.max_shifts_per_week = max_w
            msg = "수정 완료."

        save_employees(self._employees)
        self._load_table()
        self.changed = True
        QMessageBox.information(self, "완료", msg)

# Employee 생성 헬퍼 (직접 의존 방지: dict 언패킹과 동일 속성명 사용)
def _mk_employee(**kwargs):
    class _E:
        def __init__(self, **kw): self.__dict__.update(kw)
    return _E(**kwargs)
