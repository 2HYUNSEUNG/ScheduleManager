# cli/schedule_menu.py
from schedule_manager.data.data_manager import load_schedules, save_schedules, load_employees
from schedule_manager.models.schedule import DailySchedule
from schedule_manager.utils.input_handler import get_input
from schedule_manager.utils.parse_utils import parse_id_list
from schedule_manager.exceptions import CancelAction, GoBackAction
from datetime import datetime

def schedule_menu():
    while True:
        print("\n[일정 관리]")
        print("1. 일정 보기")
        print("2. 일정 추가/수정")
        print("3. 휴업 설정")
        print("4. 일정 삭제")
        print("0. 메인 메뉴로")

        try:
            choice = get_input("선택")
            if choice == "1":
                show_schedule()
            elif choice == "2":
                add_or_edit_schedule()
            elif choice == "3":
                close_day()
            elif choice == "4":
                delete_schedule_menu()  # ← 추가
            elif choice == "0":
                break
            else:
                print("잘못된 선택.")
        except GoBackAction:
            print("이전 메뉴로 이동")
        except CancelAction:
            print("메인 메뉴로 이동")


def show_schedule():
    schedules = load_schedules()
    for date, sch in sorted(schedules.items()):
        print(f"{date} | A: {sch.working['A']} | B: {sch.working['B']} | 휴무: {sch.holidays} | 메모: {sch.memo} | 휴업: {sch.closed}")

def add_or_edit_schedule():
    try:
        schedules = load_schedules()
        employees = load_employees()
        employee_ids = {e.id for e in employees}

        date = get_input("날짜(YYYY-MM-DD)")
        if date not in schedules:
            schedules[date] = DailySchedule(date)

        cur = schedules[date]

        # 현재값을 보여주고, 빈값이면 유지
        a_cur = ",".join(map(str, cur.working['A'])) if cur.working['A'] else ""
        b_cur = ",".join(map(str, cur.working['B'])) if cur.working['B'] else ""
        h_cur = ",".join(map(str, cur.holidays)) if cur.holidays else ""
        m_cur = cur.memo or ""
        closed_cur = "Y" if cur.closed else "N"

        a_in = get_input("A지점 근무자 (,구분)", allow_empty=True, default=a_cur)
        b_in = get_input("B지점 근무자 (,구분)", allow_empty=True, default=b_cur)
        h_in = get_input("휴무자 (,구분)", allow_empty=True, default=h_cur)
        memo_in = get_input("메모", allow_empty=True, default=m_cur)
        closed_in = get_input("휴업 여부(Y/N)", allow_empty=True, default=closed_cur)

        # 파싱: 빈값이면 기존 유지
        A = parse_id_list(a_in) if a_in != "" else cur.working['A'][:]
        B = parse_id_list(b_in) if b_in != "" else cur.working['B'][:]
        H = parse_id_list(h_in) if h_in != "" else cur.holidays[:]

        # 유효 ID만 유지
        A = [i for i in A if i in employee_ids]
        B = [i for i in B if i in employee_ids]
        H = [i for i in H if i in employee_ids]

        # 1) 지점 내 중복 제거
        A = list(dict.fromkeys(A))
        B = list(dict.fromkeys(B))
        H = list(dict.fromkeys(H))

        # 2) A/B 교차 중복 제거: A 우선, B에서 제외
        B = [i for i in B if i not in A]

        # 3) 근무자와 휴무자 충돌 제거: 근무가 우선, 휴무에서 제외
        H = [i for i in H if i not in A and i not in B]

        # 메모/휴업 처리
        memo = memo_in if memo_in != "" else cur.memo
        closed = (closed_in or closed_cur).upper().startswith("Y")

        # 저장
        cur.working['A'] = A
        cur.working['B'] = B
        cur.holidays = H
        cur.memo = memo
        cur.closed = closed

        schedules[date] = cur
        save_schedules(schedules)
        print("일정이 저장되었습니다.")

    except GoBackAction:
        print("이전 메뉴로 이동")
        return
    except CancelAction:
        print("메인 메뉴로 이동")
        return

def close_day():
    schedules = load_schedules()
    date = get_input("휴업 날짜(YYYY-MM-DD): ")
    if date not in schedules:
        schedules[date] = DailySchedule(date)
    schedules[date].closed = True
    save_schedules(schedules)
    print(f"{date} 휴업 처리 완료")

def employee_schedule_menu():
    try:
        employees = load_employees()
        if not employees:
            print("직원이 없습니다. 먼저 직원을 추가해주세요.")
            return

        # 직원 목록 간단 출력
        print("\n[직원 목록]")
        for e in employees:
            print(f"{e.id} | {e.name} | {e.role} | {e.skill_level} | {e.home_branch}")

        emp_id = int(get_input("\n조회할 직원 ID"))
        emp = next((x for x in employees if x.id == emp_id), None)
        if not emp:
            print("해당 ID의 직원이 없습니다.")
            return

        schedules = load_schedules()
        if not schedules:
            print("스케줄 데이터가 없습니다.")
            return

        # 기간 선택(빈값 허용 → 전체 범위)
        all_dates = sorted(schedules.keys())
        min_date, max_date = all_dates[0], all_dates[-1]

        start = get_input(f"시작일(YYYY-MM-DD) [기본 {min_date}]", allow_empty=True, default=min_date)
        end   = get_input(f"종료일(YYYY-MM-DD) [기본 {max_date}]", allow_empty=True, default=max_date)
        start = start or min_date
        end   = end or max_date

        print(f"\n[{emp.name}님의 스케줄] {start} ~ {end}")

        # 날짜별 상태 계산
        rows = _build_employee_rows(emp_id, schedules, start, end)

        # 출력
        _print_employee_rows(rows)

        # 합계
        total_work = sum(1 for r in rows if r['status'].startswith('근무'))
        total_work_A = sum(1 for r in rows if r['status'] == '근무(A)')
        total_work_B = sum(1 for r in rows if r['status'] == '근무(B)')
        total_off = sum(1 for r in rows if r['status'] == '휴무')
        total_closed = sum(1 for r in rows if r['status'] == '휴업')
        total_none = sum(1 for r in rows if r['status'] == '미지정')

        print("\n[합계]")
        print(f"근무: {total_work}일 (A: {total_work_A} / B: {total_work_B})")
        print(f"휴무: {total_off}일")
        print(f"휴업: {total_closed}일")
        print(f"미지정: {total_none}일")

    except GoBackAction:
        print("이전 메뉴로 이동")
    except CancelAction:
        print("메인 메뉴로 이동")


def _build_employee_rows(emp_id: int, schedules: dict, start: str, end: str) -> list[dict]:
    """
    날짜 범위 내에서 해당 직원의 상태를 행 리스트로 만든다.
    상태 우선순위: 휴업 > 근무(A/B) > 휴무 > 미지정
    """
    # 날짜 정렬 및 범위 필터
    dates = sorted(d for d in schedules.keys() if start <= d <= end)

    rows = []
    for d in dates:
        sch = schedules[d]
        if sch.closed:
            rows.append({"date": d, "status": "휴업", "memo": sch.memo or ""})
            continue

        in_A = emp_id in sch.working.get('A', [])
        in_B = emp_id in sch.working.get('B', [])
        in_H = emp_id in sch.holidays

        if in_A and in_B:
            # 방어: 설계상 A/B 중복은 없도록 했지만, 혹시 모를 데이터 깨짐 대비
            rows.append({"date": d, "status": "근무(A/B)", "memo": sch.memo or ""})
        elif in_A:
            rows.append({"date": d, "status": "근무(A)", "memo": sch.memo or ""})
        elif in_B:
            rows.append({"date": d, "status": "근무(B)", "memo": sch.memo or ""})
        elif in_H:
            rows.append({"date": d, "status": "휴무", "memo": sch.memo or ""})
        else:
            rows.append({"date": d, "status": "미지정", "memo": sch.memo or ""})

    return rows


def _print_employee_rows(rows: list[dict]):
    if not rows:
        print("(해당 기간 데이터가 없습니다.)")
        return
    # 단순 표 출력
    print("\n날짜         상태       메모")
    print("-" * 40)
    for r in rows:
        date = r['date']
        status = r['status']
        memo = r['memo'] or ""
        print(f"{date}  {status:<8}  {memo}")

def _select_employee_and_range():
    employees = load_employees()
    if not employees:
        print("직원이 없습니다. 먼저 직원을 추가해주세요.")
        return (None, None, None)   # ← 항상 3-튜플

    print("\n[직원 목록]")
    for e in employees:
        print(f"{e.id} | {e.name} | {e.role} | {e.skill_level} | {e.home_branch}")

    try:
        emp_id = int(get_input("\n조회할 직원 ID"))
    except (ValueError, GoBackAction, CancelAction):
        # 입력 실수/취소/뒤로 → 상위에서 판단하도록 None 튜플
        return (None, None, None)

    emp = next((x for x in employees if x.id == emp_id), None)
    if not emp:
        print("해당 ID의 직원이 없습니다.")
        return (None, None, None)

    schedules = load_schedules()
    if not schedules:
        print("스케줄 데이터가 없습니다.")
        return (None, None, None)   # ← 여기서도 3-튜플

    all_dates = sorted(schedules.keys())
    min_date, max_date = all_dates[0], all_dates[-1]

    start = get_input(f"시작일(YYYY-MM-DD) [기본 {min_date}]", allow_empty=True, default=min_date) or min_date
    end   = get_input(f"종료일(YYYY-MM-DD) [기본 {max_date}]", allow_empty=True, default=max_date) or max_date

    return (emp, schedules, (start, end))

def _iter_dates_in_range(schedules: dict, start: str, end: str):
    for d in sorted(schedules.keys()):
        if start <= d <= end:
            yield d, schedules[d]

def employee_work_schedule_menu():
    """직원별 '근무만' 필터 조회 (A/B 모두 포함, 휴업/휴무/미지정 제외)"""
    try:
        res = _select_employee_and_range()
        if not res or res[0] is None:
            return
        emp, schedules, (start, end) = res

        rows = []
        for date, sch in _iter_dates_in_range(schedules, start, end):
            if sch.closed:
                continue
            in_A = emp.id in sch.working.get('A', [])
            in_B = emp.id in sch.working.get('B', [])
            if in_A or in_B:
                status = "근무(A)" if in_A else "근무(B)"
                rows.append({"date": date, "status": status, "memo": sch.memo or ""})

        if not rows:
            print(f"\n[{emp.name}] 기간 {start}~{end} 근무 데이터가 없습니다.")
            return

        print(f"\n[{emp.name}] 근무만 보기: {start} ~ {end}")
        print("\n날짜         상태       메모")
        print("-" * 40)
        for r in rows:
            print(f"{r['date']}  {r['status']:<8}  {r['memo']}")

        # 합계
        total_work = len(rows)
        total_work_A = sum(1 for r in rows if r['status'] == '근무(A)')
        total_work_B = total_work - total_work_A
        print("\n[합계]")
        print(f"근무: {total_work}일 (A: {total_work_A} / B: {total_work_B})")

    except GoBackAction:
        print("이전 메뉴로 이동")
    except CancelAction:
        print("메인 메뉴로 이동")

def employee_off_schedule_menu():
    """직원별 '휴무만' 필터 조회 (휴업/근무/미지정 제외)"""
    try:
        res = _select_employee_and_range()
        if not res or res[0] is None:
            return
        emp, schedules, (start, end) = res

        rows = []
        for date, sch in _iter_dates_in_range(schedules, start, end):
            if sch.closed:
                continue
            if emp.id in sch.holidays:
                rows.append({"date": date, "status": "휴무", "memo": sch.memo or ""})

        if not rows:
            print(f"\n[{emp.name}] 기간 {start}~{end} 휴무 데이터가 없습니다.")
            return

        print(f"\n[{emp.name}] 휴무만 보기: {start} ~ {end}")
        print("\n날짜         상태       메모")
        print("-" * 40)
        for r in rows:
            print(f"{r['date']}  {r['status']:<8}  {r['memo']}")

        # 합계
        print("\n[합계]")
        print(f"휴무: {len(rows)}일")

    except GoBackAction:
        print("이전 메뉴로 이동")
    except CancelAction:
        print("메인 메뉴로 이동")

def delete_schedule_menu():
    while True:
        print("\n[일정 삭제]")
        print("1. 하루 삭제")
        print("2. 기간(시작일~종료일) 삭제")
        print("3. 월 전체 삭제")
        print("0. 이전 메뉴로")
        try:
            choice = get_input("선택")
            if choice == "1":
                delete_one_day()
            elif choice == "2":
                delete_range()
            elif choice == "3":
                delete_month()
            elif choice == "0":
                return
            else:
                print("잘못된 선택.")
        except GoBackAction:
            print("이전 메뉴로 이동")
            return
        except CancelAction:
            print("메인 메뉴로 이동")
            return


def _confirm_and_apply(keys_to_delete: list[str]) -> None:
    if not keys_to_delete:
        print("삭제할 일정이 없습니다.")
        return
    print(f"삭제 예정 건수: {len(keys_to_delete)}")
    # 간단 프리뷰 최대 10건
    preview = keys_to_delete[:10]
    print("미리보기:", ", ".join(preview) + (" ..." if len(keys_to_delete) > 10 else ""))

    ans = get_input("정말 삭제하시겠습니까? (Y/N)")
    if ans.strip().upper().startswith("Y"):
        schedules = load_schedules()
        for k in keys_to_delete:
            schedules.pop(k, None)
        save_schedules(schedules)
        print(f"{len(keys_to_delete)}건 삭제 완료.")
    else:
        print("삭제 취소.")


def delete_one_day():
    try:
        schedules = load_schedules()
        if not schedules:
            print("스케줄 데이터가 없습니다.")
            return
        date = get_input("삭제할 날짜(YYYY-MM-DD)")
        keys = [date] if date in schedules else []
        _confirm_and_apply(keys)
    except GoBackAction:
        print("이전 메뉴로 이동")
    except CancelAction:
        print("메인 메뉴로 이동")


def delete_range():
    try:
        schedules = load_schedules()
        if not schedules:
            print("스케줄 데이터가 없습니다.")
            return

        all_dates = sorted(schedules.keys())
        min_date, max_date = all_dates[0], all_dates[-1]

        start = get_input(f"시작일(YYYY-MM-DD) [기본 {min_date}]", allow_empty=True, default=min_date) or min_date
        end   = get_input(f"종료일(YYYY-MM-DD) [기본 {max_date}]", allow_empty=True, default=max_date) or max_date

        # 간단한 유효성
        try:
            sd = datetime.strptime(start, "%Y-%m-%d")
            ed = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            print("날짜 형식이 올바르지 않습니다.")
            return
        if sd > ed:
            print("시작일이 종료일보다 이후입니다.")
            return

        keys = [d for d in schedules.keys() if start <= d <= end]
        keys.sort()
        _confirm_and_apply(keys)
    except GoBackAction:
        print("이전 메뉴로 이동")
    except CancelAction:
        print("메인 메뉴로 이동")


def delete_month():
    try:
        schedules = load_schedules()
        if not schedules:
            print("스케줄 데이터가 없습니다.")
            return

        # 입력 예: 2025-08
        ym = get_input("삭제할 월(YYYY-MM)")
        # 간단 유효성
        try:
            datetime.strptime(ym, "%Y-%m")
        except ValueError:
            print("형식이 올바르지 않습니다. 예) 2025-08")
            return

        prefix = ym + "-"
        keys = [d for d in schedules.keys() if d.startswith(prefix)]
        keys.sort()
        _confirm_and_apply(keys)
    except GoBackAction:
        print("이전 메뉴로 이동")
    except CancelAction:
        print("메인 메뉴로 이동")