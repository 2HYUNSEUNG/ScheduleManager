# gui/day_editor.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QCheckBox, QPushButton, QListWidget, QListWidgetItem, QMessageBox,
)
from schedule_manager.models.schedule import DailySchedule

def open_day_editor(parent, date_key: str, employees, schedules) -> bool:
    dlg = DayEditorDialog(parent, date_key, employees, schedules)
    ok = dlg.exec()
    return bool(ok)

class DayEditorDialog(QDialog):
    def __init__(self, parent, date_key, employees, schedules):
        super().__init__(parent)
        self.setWindowTitle(f"{date_key} 편집")
        self.date_key = date_key
        self.employees = employees
        self.schedules = schedules
        self.changed = False

        # 이름 <-> ID 매핑
        self.name_to_id = {e.name.strip(): e.id for e in employees}
        self.id_to_name = {e.id: e.name.strip() for e in employees}

        sch = schedules.get(date_key) or DailySchedule(date_key)
        self.sch = sch

        # 기존 데이터에서 이름으로 변환
        a_names = ",".join(self.id_to_name.get(i, str(i)) for i in sch.working.get("OS", []))
        b_names = ",".join(self.id_to_name.get(i, str(i)) for i in sch.working.get("HC", []))
        h_names = ",".join(self.id_to_name.get(i, str(i)) for i in (sch.holidays or []))
        memo  = sch.memo or ""

        v = QVBoxLayout(self)

        # 직원 미리보기
        v.addWidget(QLabel("직원(ID | 이름 | 직급 | 숙련 | 지점)"))
        self.listbox = QListWidget()
        for e in employees:
            skill = "조리" if getattr(e, "skill_level","") in ("C","cook") else "비조리"
            QListWidgetItem(f"{e.id} | {e.name} | {e.role} | {skill} | {e.home_branch}", self.listbox)
        v.addWidget(self.listbox)

        # 입력 필드 (이름 입력)
        def row(label, init_value=""):
            box = QHBoxLayout()
            box.addWidget(QLabel(label))
            line = QLineEdit(init_value)
            box.addWidget(line)
            v.addLayout(box)
            return line

        self.a_edit = row("OS 근무", a_names)
        self.b_edit = row("HC 근무", b_names)
        self.h_edit = row("휴무 ", h_names)

        v.addWidget(QLabel("메모"))
        self.memo_edit = QTextEdit(memo)
        v.addWidget(self.memo_edit)

        self.closed_cb = QCheckBox("휴업")
        self.closed_cb.setChecked(bool(sch.closed))
        v.addWidget(self.closed_cb)

        self.closed_cb.toggled.connect(self.on_closed_toggled)
        self.on_closed_toggled(self.closed_cb.isChecked())

        # 버튼
        btns = QHBoxLayout()
        delete_btn = QPushButton("삭제")
        save_btn = QPushButton("저장")
        cancel_btn = QPushButton("취소")
        btns.addWidget(delete_btn)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        v.addLayout(btns)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.on_save)
        delete_btn.clicked.connect(self.on_delete)

    def parse_names(self, text):
        """
        쉼표로 구분된 이름을 ID 리스트로 변환.
        이름이 없으면 무시, 중복 제거.
        """
        out, seen = [], set()
        for tok in text.split(','):
            t = tok.strip()
            if not t:
                continue
            emp_id = self.name_to_id.get(t)
            if emp_id and emp_id not in seen:
                seen.add(emp_id)
                out.append(emp_id)
        return out

    def on_save(self):
        # 휴업이면 강제로 모두 비움
        if self.closed_cb.isChecked():
            OS, HC, H = [], [], []
        else:
            OS = self.parse_names(self.a_edit.text())
            HC = self.parse_names(self.b_edit.text())
            H = self.parse_names(self.h_edit.text())
            # 교차 중복 제거(OS 우선), 근무/휴무 충돌 제거(근무 우선)
            HC = [i for i in HC if i not in OS]
            H = [i for i in H if i not in OS and i not in HC]

        self.sch.working['OS'] = OS
        self.sch.working['HC'] = HC
        self.sch.holidays = H
        self.sch.memo = self.memo_edit.toPlainText().strip()
        self.sch.closed = self.closed_cb.isChecked()

        self.schedules[self.date_key] = self.sch
        self.changed = True
        QMessageBox.information(self, "저장", "일정이 저장되었습니다.")
        self.accept()

    def on_delete(self):
        if self.date_key in self.schedules:
            self.schedules.pop(self.date_key, None)
            self.changed = True
        QMessageBox.information(self, "삭제", "일정이 삭제되었습니다.")
        self.accept()

    def on_closed_toggled(self, checked: bool):
        # 휴업 체크 시 입력 필드 비우고 비활성화
        for line in (self.a_edit, self.b_edit, self.h_edit):
            if checked:
                line.clear()
            line.setDisabled(checked)
