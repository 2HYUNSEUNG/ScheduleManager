# gui/calendar_widget.py
import calendar
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QTextEdit, QFrame, QMenu, QHBoxLayout
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QTextCursor, QTextBlockFormat, QCursor

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

        # ID → 이름 매핑
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
                v.setSpacing(6)

                if day == 0:
                    self.grid.addWidget(cell, r, c)
                    continue

                # ------- 헤더(날짜 + 메모 아이콘) -------
                hdr = QHBoxLayout()
                hdr.setContentsMargins(0, 0, 0, 0)
                hdr.setSpacing(4)

                # 메모 아이콘(기본 숨김)
                memo_icon = QLabel("📝")
                memo_icon.setVisible(False)
                memo_icon.setAlignment(Qt.AlignTop | Qt.AlignRight)

                day_lbl = QLabel(str(day))
                day_lbl.setAlignment(Qt.AlignTop | Qt.AlignRight)

                # 우측 정렬: 스트레치 먼저, 그 다음 아이콘/날짜
                hdr.addStretch(1)
                hdr.addWidget(memo_icon)
                hdr.addWidget(day_lbl)
                v.addLayout(hdr)

                # ------- 내용 -------
                key = f"{year:04d}-{month:02d}-{day:02d}"
                sch = schedules.get(key)
                text = QTextEdit()
                text.setReadOnly(True)
                text.setTextInteractionFlags(Qt.NoTextInteraction)  # 마우스로 선택 불가
                text.setFocusPolicy(Qt.NoFocus)                     # 포커스 안 받게
                text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                text.setContextMenuPolicy(Qt.NoContextMenu)

                content = []
                memo = ""
                if sch:
                    if getattr(sch, "closed", False):
                        content.append("[휴업]")
                    a = ids_to_names(sch.working.get('OS', []))
                    b = ids_to_names(sch.working.get('HC', []))
                    h = ids_to_names(getattr(sch, "holidays", []))
                    if a: content.append("OS: " + ", ".join(a))
                    if b: content.append("HC: " + ", ".join(b))
                    if h: content.append("휴: " + ", ".join(h))
                    memo = getattr(sch, "memo", "") or ""
                    if memo:
                        content.append(f"메모: {memo}")

                # 메모가 있으면 아이콘 표시 + 툴팁에 메모 노출
                if memo:
                    memo_icon.setVisible(True)
                    memo_icon.setToolTip(memo)

                text.setPlainText("\n".join(content))
                v.addWidget(text)

                # 줄간격 135%
                cur = text.textCursor()
                cur.select(QTextCursor.Document)
                fmt = QTextBlockFormat()
                try:
                    fmt.setLineHeight(135.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight)
                except TypeError:
                    fmt.setLineHeight(135.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                cur.mergeBlockFormat(fmt)
                cur.clearSelection()
                cur.movePosition(QTextCursor.Start)
                text.setTextCursor(cur)

                # 더블클릭 → 편집
                def open_editor(_=None, y=year, m=month, d=day):
                    self.on_day_open(y, m, d)
                cell.mouseDoubleClickEvent = lambda ev, fn=open_editor: fn()

                # 우클릭 → 해당 일정 삭제
                def ctx_menu(point: QPoint, y=year, m=month, d=day):
                    if not self.on_day_delete:
                        return
                    menu = QMenu(self)
                    act_del = menu.addAction("해당 일정 삭제")
                    # 마우스 현재 위치에 표시
                    act = menu.exec(QCursor.pos())
                    if act == act_del:
                        self.on_day_delete(f"{y:04d}-{m:02d}-{d:02d}")

                cell.setContextMenuPolicy(Qt.CustomContextMenu)
                cell.customContextMenuRequested.connect(ctx_menu)

                self.grid.addWidget(cell, r, c)
