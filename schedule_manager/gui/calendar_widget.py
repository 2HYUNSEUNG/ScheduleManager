# gui/calendar_widget.py
import calendar
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QTextEdit, QFrame, QMenu
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QTextCursor, QTextBlockFormat

class CalendarWidget(QWidget):
    def __init__(self, on_day_open, on_day_delete=None):
        super().__init__()
        self.on_day_open = on_day_open
        self.on_day_delete = on_day_delete
        self.vbox = QVBoxLayout(self)

        header = QGridLayout()
        self.vbox.addLayout(header)
        weekdays = ("일","월","화","수","목","금","토")
        for c, w in enumerate(weekdays):
            lbl = QLabel(w); lbl.setAlignment(Qt.AlignCenter)
            header.addWidget(lbl, 0, c)

        self.grid = QGridLayout()
        self.vbox.addLayout(self.grid)

    def clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def render_month(self, year, month, employees, schedules):
        self.clear_grid()
        cal = calendar.Calendar(firstweekday=6)  # Sunday
        weeks = cal.monthdayscalendar(year, month)

        # 🔹 ID → 이름 매핑
        id_to_name = {getattr(e, "id"): getattr(e, "name") for e in (employees or [])}

        def ids_to_names(id_list):
            if not id_list:
                return []
            return [id_to_name.get(i, str(i)) for i in id_list]

        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                cell = QFrame()
                cell.setFrameShape(QFrame.StyledPanel)
                v = QVBoxLayout(cell)
                if day == 0:
                    self.grid.addWidget(cell, r, c)
                    continue

                # 날짜
                day_lbl = QLabel(str(day))
                day_lbl.setAlignment(Qt.AlignTop | Qt.AlignRight)
                v.addWidget(day_lbl)

                # 내용
                key = f"{year:04d}-{month:02d}-{day:02d}"
                sch = schedules.get(key)
                text = QTextEdit()
                text.setReadOnly(True)
                content = []
                if sch:
                    if getattr(sch, "closed", False):
                        content.append("[휴업]")
                    a = ids_to_names(sch.working.get('OS', []))
                    b = ids_to_names(sch.working.get('HC', []))
                    h = ids_to_names(getattr(sch, "holidays", []))
                    if a: content.append("OS: " + ", ".join(a))
                    if b: content.append("HC: " + ", ".join(b))
                    if h: content.append("휴: " + ", ".join(h))
                    memo = getattr(sch, "memo", "")
                    if memo: content.append(f"메모: {memo}")

                text.setTextInteractionFlags(Qt.NoTextInteraction)  # 마우스로 선택 불가
                text.setFocusPolicy(Qt.NoFocus)  # 포커스 안 받게
                text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                text.setContextMenuPolicy(Qt.NoContextMenu)

                text.setPlainText("\n".join(content))
                v.addWidget(text)

                cur = text.textCursor()
                cur.select(QTextCursor.Document)
                fmt = QTextBlockFormat()
                try:
                    fmt.setLineHeight(135.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight)
                except TypeError:
                    # 일부 환경에서는 .value가 필요할 수 있음
                    fmt.setLineHeight(135.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                cur.mergeBlockFormat(fmt)

                v.setSpacing(6)  # 날짜 라벨과 텍스트 사이 간격 소폭 증가

                # 더블클릭 → 편집
                def open_editor(_=None, y=year, m=month, d=day):
                    self.on_day_open(y, m, d)
                cell.mouseDoubleClickEvent = lambda ev, fn=open_editor: fn()

                # 우클릭 메뉴 → 이 날 삭제
                def ctx_menu(point: QPoint, y=year, m=month, d=day):
                    if not self.on_day_delete:
                        return
                    menu = QMenu(self)
                    act_del = menu.addAction("이 날 일정 삭제")
                    act = menu.exec(cell.mapToGlobal(point))
                    if act == act_del:
                        self.on_day_delete(f"{y:04d}-{m:02d}-{d:02d}")

                cell.setContextMenuPolicy(Qt.CustomContextMenu)
                cell.customContextMenuRequested.connect(ctx_menu)

                self.grid.addWidget(cell, r, c)
