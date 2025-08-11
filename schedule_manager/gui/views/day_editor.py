# gui/day_editor.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QCheckBox, QPushButton, QListWidget, QListWidgetItem, QMessageBox,
    QGroupBox, QGridLayout, QComboBox
)
from PySide6.QtCore import Qt
from schedule_manager.models.schedule import DailySchedule

ROLE_LABELS = ["전체", "사장", "매니저", "직원"]
SKILL_LABELS = ["전체", "조리(○)", "비조리(X)"]
BRANCH_LABELS = ["전체", "OS", "HC"]

def open_day_editor(parent, date_key: str, employees, schedules) -> bool:
    dlg = DayEditorDialog(parent, date_key, employees, schedules)
    ok = dlg.exec()
    return bool(ok)

class DayEditorDialog(QDialog):
    """
    클릭 중심 수동 배정:
      - OS / HC / 휴무 3열 체크박스 리스트 (이름 영역 클릭도 토글)
      - 상단 필터(검색/직급/숙련/지점)
      - OS/HC는 최대 2명(저장 시 검증/자동 축소 옵션)
      - OS/HC/휴무는 직원 1명이 동시 체크 불가(상호 배제)
      - 휴업 체크 시 모든 리스트 비우고 잠금
      - 저장 시 중복 제거(우선순위: OS/HC > 휴무)
    """
    def __init__(self, parent, date_key, employees, schedules):
        super().__init__(parent)
        self.setWindowTitle(f"{date_key} 일정 편집")
        self.date_key = date_key
        self.employees = list(employees)
        self.schedules = schedules

        self.sch = schedules.get(date_key) or DailySchedule(date_key)
        self.emp_by_id = {e.id: e for e in self.employees}

        # id -> QListWidgetItem 매핑(상호 배제 제어용)
        self.item_map = {"OS": {}, "HC": {}, "OFF": {}}

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        # 상단 필터
        filter_box = QGroupBox("필터")
        grid = QGridLayout(filter_box); r = 0
        self.ed_search = QLineEdit(); self.ed_search.setPlaceholderText("이름 검색")
        self.cmb_role = QComboBox();  self.cmb_role.addItems(ROLE_LABELS)
        self.cmb_skill = QComboBox(); self.cmb_skill.addItems(SKILL_LABELS)
        self.cmb_branch = QComboBox(); self.cmb_branch.addItems(BRANCH_LABELS)
        grid.addWidget(QLabel("검색"), r, 0); grid.addWidget(self.ed_search, r, 1)
        grid.addWidget(QLabel("직급"), r, 2); grid.addWidget(self.cmb_role, r, 3)
        grid.addWidget(QLabel("숙련"), r, 4); grid.addWidget(self.cmb_skill, r, 5)
        grid.addWidget(QLabel("지점"), r, 6); grid.addWidget(self.cmb_branch, r, 7)
        self.ed_search.textChanged.connect(self._apply_filter)
        self.cmb_role.currentIndexChanged.connect(self._apply_filter)
        self.cmb_skill.currentIndexChanged.connect(self._apply_filter)
        self.cmb_branch.currentIndexChanged.connect(self._apply_filter)
        v.addWidget(filter_box)

        # 휴업
        self.closed_cb = QCheckBox("휴업")
        self.closed_cb.setChecked(bool(self.sch.closed))
        v.addWidget(self.closed_cb)

        # 중앙: OS / HC / 휴무 3열
        mid = QHBoxLayout(); mid.setSpacing(8)
        self.list_os  = self._make_list_group("OS",  "OS 근무", limit=2)
        self.list_hc  = self._make_list_group("HC",  "HC 근무", limit=2)
        self.list_off = self._make_list_group("OFF", "휴무",   limit=None)
        mid.addWidget(self.list_os["box"], 1)
        mid.addWidget(self.list_hc["box"], 1)
        mid.addWidget(self.list_off["box"], 1)
        v.addLayout(mid)

        # 하단: 메모
        memo_row = QHBoxLayout()
        memo_row.addWidget(QLabel("메모"))
        self.memo_edit = QTextEdit(self.sch.memo or ""); self.memo_edit.setFixedHeight(70)
        memo_row.addWidget(self.memo_edit, 1)
        v.addLayout(memo_row)

        # 버튼
        btns = QHBoxLayout()
        self.btn_clear_all = QPushButton("모두 해제")
        self.btn_swap      = QPushButton("OS ↔ HC 교환")
        self.btn_delete    = QPushButton("삭제")
        self.btn_cancel    = QPushButton("취소")
        self.btn_save      = QPushButton("저장")
        btns.addWidget(self.btn_clear_all)
        btns.addWidget(self.btn_swap)
        btns.addStretch(1)
        btns.addWidget(self.btn_delete)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_save)
        v.addLayout(btns)

        # 데이터 바인딩
        self._fill_lists()

        # 이벤트
        self.closed_cb.toggled.connect(self._on_closed_toggled)
        self.btn_clear_all.clicked.connect(self._on_clear_all)
        self.btn_swap.clicked.connect(self._on_swap)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

        self._on_closed_toggled(self.closed_cb.isChecked())
        self.setMinimumWidth(560); self.setMinimumHeight(520)

        self._exclusive_lock = False

    # ---------- UI 유틸 ----------
    def _make_list_group(self, key: str, title: str, limit: int | None):
        box = QGroupBox(title)
        lv = QVBoxLayout(box);
        lv.setSpacing(4)
        info = QLabel("(0명 선택)");
        info.setStyleSheet("color:#666; font-size:11px;")
        lv.addWidget(info)

        listw = QListWidget()
        listw.setUniformItemSizes(True)
        listw.setAlternatingRowColors(True)
        listw.setSelectionMode(QListWidget.NoSelection)
        lv.addWidget(listw, 1)

        # 클릭 전 상태 기억용
        last_pressed_state = {"state": None}

        def on_item_pressed(item: QListWidgetItem):
            # 클릭 직전 상태 저장 (체크박스 직접 클릭 시 Qt가 자동 토글하므로 비교 기준)
            last_pressed_state["state"] = item.checkState()

        def on_item_clicked(item: QListWidgetItem):
            # 클릭 후 상태가 '변하지 않았다' = 텍스트/여백 클릭 → 수동 토글
            if item.checkState() == last_pressed_state["state"]:
                item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
            # 수동 토글이든 자동 토글이든 최종 처리는 itemChanged에서 한다

        def on_item_changed(item: QListWidgetItem):
            # 재진입 보호: 상호배제 처리 중이면 무시
            if getattr(self, "_exclusive_lock", False):
                return
            eid = int(item.data(Qt.UserRole))
            checked = (item.checkState() == Qt.Checked)
            self._enforce_exclusive_after_toggle(source=key, eid=eid, checked=checked)
            self._update_count_labels()

            # (선택) 제한 안내는 저장 시 검증. 여기서는 막지 않음.

        listw.itemPressed.connect(on_item_pressed)
        listw.itemClicked.connect(on_item_clicked)
        listw.itemChanged.connect(on_item_changed)

        return {"key": key, "box": box, "list": listw, "info": info, "limit": limit, "title": title}

    def _format_emp(self, e):
        cook = "○" if getattr(e, "skill_level", "") in ("C", "cook") else "X"
        return f"{e.name}    |    {e.role} / {cook} / {e.home_branch}"

    def _fill_lists(self):
        os_ids = list(self.sch.working.get("OS") or [])
        hc_ids = list(self.sch.working.get("HC") or [])
        off_ids = list(self.sch.holidays or [])

        # 초기화
        for panel in (self.list_os, self.list_hc, self.list_off):
            lw = panel["list"]
            lw.blockSignals(True); lw.clear(); lw.blockSignals(False)
        self.item_map = {"OS": {}, "HC": {}, "OFF": {}}

        # 채우기 + 매핑 저장
        def add_item(panel, e, checked):
            lw = panel["list"]
            lw.blockSignals(True)
            it = QListWidgetItem(self._format_emp(e))
            it.setData(Qt.UserRole, e.id)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            lw.addItem(it)
            lw.blockSignals(False)
            self.item_map[panel["key"]][e.id] = it

        for e in self.employees:
            add_item(self.list_os,  e, e.id in os_ids)
            add_item(self.list_hc,  e, e.id in hc_ids)
            add_item(self.list_off, e, e.id in off_ids)

        # 초기 상호 배제 상태 반영
        for eid in self.emp_by_id.keys():
            # 우선순위: OS/HC가 체크되어 있으면 OFF는 막힘, 둘 다 해제일 때만 OFF 사용 가능
            if self.item_map["OS"][eid].checkState() == Qt.Checked:
                self._set_enabled(self.item_map["HC"][eid],  False)
                self._set_enabled(self.item_map["OFF"][eid], False)
            elif self.item_map["HC"][eid].checkState() == Qt.Checked:
                self._set_enabled(self.item_map["OS"][eid],  False)
                self._set_enabled(self.item_map["OFF"][eid], False)
            elif self.item_map["OFF"][eid].checkState() == Qt.Checked:
                self._set_enabled(self.item_map["OS"][eid],  False)
                self._set_enabled(self.item_map["HC"][eid],  False)

        self._apply_filter()
        self._update_count_labels()

    def _apply_filter(self):
        term   = self.ed_search.text().strip()
        role   = self.cmb_role.currentText()
        skill  = self.cmb_skill.currentText()
        branch = self.cmb_branch.currentText()

        def visible(e):
            if term and term not in e.name: return False
            if role  != "전체" and e.role         != role:   return False
            if branch!= "전체" and e.home_branch  != branch: return False
            if skill != "전체":
                want_cook = skill.startswith("조리")
                is_cook = getattr(e, "skill_level", "") in ("C", "cook")
                if want_cook != is_cook: return False
            return True

        for panel in (self.list_os, self.list_hc, self.list_off):
            lw = panel["list"]
            for i in range(lw.count()):
                it = lw.item(i)
                e  = self.emp_by_id.get(int(it.data(Qt.UserRole)))
                lw.setRowHidden(i, not visible(e))

    # ---------- 상호 배제 ----------
    def _set_enabled(self, item: QListWidgetItem, enabled: bool):
        lw = item.listWidget()
        if lw:
            lw.blockSignals(True)
        try:
            flags = item.flags()
            if enabled:
                item.setFlags((flags | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable))
            else:
                # 비활성화 + 체크 해제(있다면)
                item.setFlags((flags | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEnabled)
                if item.checkState() == Qt.Checked:
                    item.setCheckState(Qt.Unchecked)  # 신호 차단 중이므로 재귀 없음
        finally:
            if lw:
                lw.blockSignals(False)

    def _enforce_exclusive_after_toggle(self, source: str, eid: int, checked: bool):
        if self._exclusive_lock:
            return
        self._exclusive_lock = True
        try:
            others = [k for k in ("OS", "HC", "OFF") if k != source]
            if checked:
                # source에 체크되면 나머지 두 패널은 비활성화(+체크해제)
                for k in others:
                    it = self.item_map[k][eid]
                    self._set_enabled(it, False)
            else:
                # source에서 해제 → 다른 패널들 활성화
                for k in others:
                    it = self.item_map[k][eid]
                    self._set_enabled(it, True)
                # 단, 다른 한 쪽이 이미 체크였다면(예: OFF가 체크) 반대편은 막는다
                checked_others = [k for k in others if self.item_map[k][eid].checkState() == Qt.Checked]
                if checked_others:
                    for k in others:
                        if k not in checked_others:
                            self._set_enabled(self.item_map[k][eid], False)
        finally:
            self._exclusive_lock = False

    def _checked_ids(self, listw: QListWidget):
        ids = []
        for i in range(listw.count()):
            it = listw.item(i)
            if it.checkState() == Qt.Checked:
                ids.append(int(it.data(Qt.UserRole)))
        return ids

    def _update_count_labels(self):
        self.list_os["info"].setText(f"({len(self._checked_ids(self.list_os['list']))}명 선택)")
        self.list_hc["info"].setText(f"({len(self._checked_ids(self.list_hc['list']))}명 선택)")
        self.list_off["info"].setText(f"({len(self._checked_ids(self.list_off['list']))}명 선택)")

    # ---------- 액션 ----------
    def _on_clear_all(self):
        for key, panel in (("OS", self.list_os), ("HC", self.list_hc), ("OFF", self.list_off)):
            lw = panel["list"]
            lw.blockSignals(True)
            for i in range(lw.count()):
                it = lw.item(i); it.setCheckState(Qt.Unchecked)
            lw.blockSignals(False)
        # 전체 활성화
        for eid in self.emp_by_id.keys():
            self._set_enabled(self.item_map["OS"][eid],  True)
            self._set_enabled(self.item_map["HC"][eid],  True)
            self._set_enabled(self.item_map["OFF"][eid], True)
        self._update_count_labels()

    def _on_swap(self):
        # OS↔HC 체크 상태 교환(휴무는 유지). 상호 배제에 맞춰 다시 enable/disable.
        os_checked = set(self._checked_ids(self.list_os["list"]))
        hc_checked = set(self._checked_ids(self.list_hc["list"]))

        # 모두 해제
        for panel in (self.list_os, self.list_hc):
            lw = panel["list"]
            lw.blockSignals(True)
            for i in range(lw.count()):
                lw.item(i).setCheckState(Qt.Unchecked)
            lw.blockSignals(False)

        # 다시 체크
        def set_checked(panel_key: str, ids):
            lw = {"OS": self.list_os["list"], "HC": self.list_hc["list"]}[panel_key]
            lw.blockSignals(True)
            for i in range(lw.count()):
                eid = int(lw.item(i).data(Qt.UserRole))
                if eid in ids:
                    lw.item(i).setCheckState(Qt.Checked)
            lw.blockSignals(False)

        set_checked("OS", hc_checked)
        set_checked("HC", os_checked)
        # OFF 체크는 유지됨. 이제 전체 enable/disable 상태를
        # 현재 체크 결과 기준으로 '전면 재계산'하여 잔여 블락을 해제/적용
        self._refresh_exclusive_states_all()

        self._update_count_labels()

    def _on_closed_toggled(self, checked: bool):
        for panel in (self.list_os, self.list_hc, self.list_off):
            panel["box"].setDisabled(checked)
            if checked:
                lw = panel["list"]
                lw.blockSignals(True)
                for i in range(lw.count()):
                    lw.item(i).setCheckState(Qt.Unchecked)
                lw.blockSignals(False)
        self.memo_edit.setDisabled(False)

    def _on_delete(self):
        if self.date_key in self.schedules:
            self.schedules.pop(self.date_key, None)
        QMessageBox.information(self, "삭제", "일정이 삭제되었습니다.")
        self.accept()

    def _on_save(self):
        if self.closed_cb.isChecked():
            self.sch.working["OS"] = []
            self.sch.working["HC"] = []
            self.sch.holidays = []
            self.sch.memo = self.memo_edit.toPlainText().strip()
            self.sch.closed = True
            self.schedules[self.date_key] = self.sch
            QMessageBox.information(self, "저장", "휴업으로 저장되었습니다.")
            self.accept()
            return

        os_ids  = self._checked_ids(self.list_os["list"])
        hc_ids  = self._checked_ids(self.list_hc["list"])
        off_ids = self._checked_ids(self.list_off["list"])

        # 상호 배제는 이미 UI에서 강제되지만, 저장 직전에도 한번 더 정리
        off_ids = [i for i in off_ids if i not in os_ids and i not in hc_ids]

        # OS/HC 인원 제한 검증
        over_parts = []
        if len(os_ids) > 2:
            over_parts.append(("OS", os_ids))
        if len(hc_ids) > 2:
            over_parts.append(("HC", hc_ids))

        if over_parts:
            parts_txt = ", ".join(f"{name}:{len(ids)}명" for name, ids in over_parts)
            QMessageBox.information(
                self, "안내",
                f"{parts_txt} 선택됨(최대 2명). 인원 초과 입니다."
            )
            return  # 저장 중단

        # 최종 반영
        self.sch.working["OS"] = os_ids
        self.sch.working["HC"] = hc_ids
        self.sch.holidays = off_ids
        self.sch.memo = self.memo_edit.toPlainText().strip()
        self.sch.closed = False

        self.schedules[self.date_key] = self.sch
        QMessageBox.information(self, "저장", "일정이 저장되었습니다.")
        self.accept()

    def _refresh_exclusive_states_all(self):
        """현재 체크 상태(OS/HC/OFF)를 기준으로 각 항목의 enable/disable을 다시 계산한다."""
        # 재귀 방지 락
        if getattr(self, "_exclusive_lock", False):
            return
        self._exclusive_lock = True
        try:
            for eid in self.emp_by_id.keys():
                it_os = self.item_map["OS"][eid]
                it_hc = self.item_map["HC"][eid]
                it_off = self.item_map["OFF"][eid]

                os_checked = (it_os.checkState() == Qt.Checked)
                hc_checked = (it_hc.checkState() == Qt.Checked)
                off_checked = (it_off.checkState() == Qt.Checked)

                # 기본은 모두 활성화
                self._set_enabled(it_os, True)
                self._set_enabled(it_hc, True)
                self._set_enabled(it_off, True)

                # 현재 상태에 따른 상호배제 적용
                if os_checked:
                    self._set_enabled(it_hc, False)
                    self._set_enabled(it_off, False)
                elif hc_checked:
                    self._set_enabled(it_os, False)
                    self._set_enabled(it_off, False)
                elif off_checked:
                    self._set_enabled(it_os, False)
                    self._set_enabled(it_hc, False)
                # 아무 데도 체크 안됐으면 모두 활성화 유지
        finally:
            self._exclusive_lock = False
