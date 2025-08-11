# data/repo.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .models import Employee, Shift

class Repo:
    def __init__(self, db_path: str = "schedule.sqlite3"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            store_pref TEXT,
            fixed_off TEXT,
            notes TEXT
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS shifts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,          -- YYYY-MM-DD
            store_id TEXT,               -- 'OS' | 'HC' | NULL(휴무)
            employee_id INTEGER NOT NULL,
            type TEXT NOT NULL,          -- '근무' | '휴무'
            memo TEXT,
            UNIQUE(date, employee_id),
            FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_shifts_emp_date ON shifts(employee_id, date);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_shifts_date ON shifts(date);")
        self.conn.commit()

    # --- Employees ---
    def upsert_employee(self, name: str, store_pref: Optional[str]=None,
                        fixed_off: Optional[str]=None, notes: Optional[str]=None) -> int:
        cur = self.conn.cursor()
        # 단순: 이름 unique 가정 안 함(동명이인 허용). 필요시 UNIQUE(name) 추가.
        cur.execute("INSERT INTO employees(name, store_pref, fixed_off, notes) VALUES(?,?,?,?)",
                    (name, store_pref, fixed_off, notes))
        self.conn.commit()
        return cur.lastrowid

    def get_employees(self) -> List[Employee]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM employees ORDER BY id;")
        rows = cur.fetchall()
        return [Employee(**dict(r)) for r in rows]

    # --- Shifts ---
    def upsert_shift(self, date: str, employee_id: int, type_: str,
                     store_id: Optional[str], memo: Optional[str]=None) -> int:
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO shifts(date, employee_id, type, store_id, memo)
        VALUES(?,?,?,?,?)
        ON CONFLICT(date, employee_id) DO UPDATE SET
            type=excluded.type,
            store_id=excluded.store_id,
            memo=COALESCE(excluded.memo, shifts.memo);
        """, (date, employee_id, type_, store_id, memo))
        self.conn.commit()
        # id 반환 위해 다시 조회
        cur.execute("SELECT id FROM shifts WHERE date=? AND employee_id=?", (date, employee_id))
        return cur.fetchone()["id"]

    def get_employee_month(self, employee_id: int, year: int, month: int) -> Dict[int, Dict]:
        """
        해당 직원의 y-m 월 데이터를 {day: {"type":..., "store":..., "memo":...}} 형태로 반환
        """
        from datetime import date
        import calendar
        days = calendar.monthrange(year, month)[1]
        yyyymm = f"{year:04d}-{month:02d}"
        cur = self.conn.cursor()
        cur.execute("""
            SELECT date, type, store_id, memo
            FROM shifts
            WHERE employee_id=? AND substr(date,1,7)=?
        """, (employee_id, yyyymm))
        result = {}
        for r in cur.fetchall():
            d = int(r["date"].split("-")[2])
            result[d] = {"type": r["type"], "store": r["store_id"], "memo": r["memo"]}
        return result

    # 간단 시드
    def seed_if_empty(self):
        if self.get_employees():
            return
        names = ["홍길동","김철수","이영희","박민수","최유리","오지점","정가게"]
        for i, n in enumerate(names):
            pref = "OS" if i % 2 == 0 else "HC"
            self.upsert_employee(n, store_pref=pref, fixed_off="Sun", notes=None)
