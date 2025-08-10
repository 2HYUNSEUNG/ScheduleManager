# logic/scheduler.py
from schedule_manager.data.data_manager import load_employees, load_schedules, save_schedules
from schedule_manager.models.schedule import DailySchedule
from datetime import datetime, timedelta
import random
import calendar
from collections import defaultdict

def auto_assign(start_date: str, days: int = 7, overwrite: bool = False, weekly_off_cap: int = 2):
    """
    자동 배정
    - overwrite=False: 기존 수동 배정은 보존, 빈 칸만 채움
    - 휴업일은 스킵
    - A/B 중복 금지
    - C 1 + N 1(조리 1 + 비조리 1) 우선, 부족하면 완화
    - 가용 인원 < 2면 남은 칸은 비워둠(추후 수동 보완)
    - 달력(일~토) 주차 기준으로 직급 무관 '직원별 주당 휴무 상한' 적용(기본 2일)
    """

    # ---- 내부 헬퍼: 해당 '월'의 달력 주차 인덱스 맵(일요일 시작, 월 경계 내만) ----
    def month_week_index_map_local(year: int, month: int) -> dict[str, int]:
        cal = calendar.Calendar(firstweekday=6)  # 6 = Sunday
        weeks = cal.monthdatescalendar(year, month)  # 각 주 7일
        idx = 0
        result = {}
        for w in weeks:
            in_month = [d for d in w if d.month == month]
            if not in_month:
                continue
            idx += 1
            for d in in_month:
                result[d.strftime("%Y-%m-%d")] = idx
        return result

    employees = load_employees()
    if not employees:
        print("직원 데이터가 없습니다. 먼저 직원을 등록해주세요.")
        return

    emp_by_id = {e.id: e for e in employees}
    schedules = load_schedules()

    # 주간 근무 횟수(월~일 기준). 시작일 기준 주간으로 초기화
    weekly_shifts = defaultdict(int)

    # 달력 주차(일~토) 기준 휴무 카운트: key=(week_idx, emp_id)
    off_count = defaultdict(int)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    # 시작 월의 주차 맵 생성
    cur_week_map = month_week_index_map_local(start_dt.year, start_dt.month)

    for d in range(days):
        cur_dt = start_dt + timedelta(days=d)
        date_str = cur_dt.strftime("%Y-%m-%d")
        weekday = cur_dt.weekday()  # 0=월 ... 6=일

        # 달이 바뀌면 해당 월의 주차 맵 재생성
        if date_str not in cur_week_map:
            cur_week_map = month_week_index_map_local(cur_dt.year, cur_dt.month)
        week_idx = cur_week_map.get(date_str, None)  # None 방어 (이론상 없어야 함)

        # 주간 리셋(월요일에 리셋)
        if weekday == 0 and d != 0:
            weekly_shifts = defaultdict(int)

        # 스케줄 객체 준비
        daily = schedules.get(date_str) or DailySchedule(date_str)
        if daily.closed:
            # 휴업일: 건드리지 않음
            schedules[date_str] = daily
            continue

        # 기존 수동 배정 보존 옵션
        if not overwrite:
            a_fixed = daily.working['OS'][:]
            b_fixed = daily.working['HC'][:]
        else:
            a_fixed, b_fixed = [], []

        # 오늘 근무 가능 후보 필터
        def is_available(e):
            # 고정 휴무(요일; 0=월..6=일)
            if weekday in getattr(e, "fixed_holidays", []):
                return False
            # 신청 휴무(특정일)
            if date_str in getattr(e, "holiday_requests", []):
                return False
            # 주간 최대 근무 초과 방지
            if weekly_shifts[e.id] >= getattr(e, "max_shifts_per_week", 6):
                return False
            return True

        available = [e for e in employees if is_available(e)]

        # 이미 다른 지점/고정 배정된 ID는 제외
        already_assigned = set(a_fixed + b_fixed)

        # 분기별 후보 생성(홈지점 우선)
        def branch_candidates(branch):
            home = [e for e in available if e.home_branch == branch and e.id not in already_assigned]
            cross = [e for e in available if e.home_branch != branch and e.id not in already_assigned]
            return home, cross

        # 각 지점에 2명 필요. 기존 수동 배정이 있으면 부족분만 채움.
        def need_for(branch, fixed_ids):
            return max(0, 2 - len(fixed_ids))

        # 조합 선택 유틸(안전)
        def choose_for_branch(branch, fixed_ids):
            """
            우선순위:
              1) 홈지점에서 C 1 + N 1
              2) 홈지점 + 크로스 혼합으로 C/N 맞추기
              3) 유형 무시하고 아무나(중복 금지)
              4) 그래도 부족하면 빈 칸 유지
            """
            need = need_for(branch, fixed_ids)
            if need <= 0:
                # 이미 2명 꽉 찬 경우
                return fixed_ids[:]

            home, cross = branch_candidates(branch)

            def split_skill(pool):
                cooks = [e for e in pool if e.skill_level == "C"]
                nocooks = [e for e in pool if e.skill_level != "C"]
                return cooks, nocooks

            chosen = fixed_ids[:]
            already = set(already_assigned) | set(chosen)

            # 1) 홈지점에서 cook+nocook 시도
            home_cooks, home_nocooks = split_skill(home)
            random.shuffle(home_cooks)
            random.shuffle(home_nocooks)

            while need > 0 and home_cooks and home_nocooks:
                c = home_cooks.pop()
                n = home_nocooks.pop()
                for cand in (c, n):
                    if cand.id not in already:
                        chosen.append(cand.id)
                        already.add(cand.id)
                        weekly_shifts[cand.id] += 1
                        need -= 1
                        if need == 0:
                            break

            # 2) 부족하면 홈+크로스 혼합으로 cook/nocook 맞추기
            if need > 0:
                cross_cooks, cross_nocooks = split_skill(cross)
                random.shuffle(cross_cooks)
                random.shuffle(cross_nocooks)

                # cook 없는 경우 보충
                if not any(emp_by_id[i].skill_level == "C" for i in chosen):
                    # 홈 cook → 없으면 크로스 cook
                    pools = [home_cooks + home, cross_cooks + cross]
                    for pool in pools:
                        for e in pool:
                            if getattr(e, "skill_level", "") == "C" and e.id not in already:
                                chosen.append(e.id)
                                already.add(e.id)
                                weekly_shifts[e.id] += 1
                                need -= 1
                                break
                        if need <= 0:
                            break

                # nocook 없는 경우 보충
                if need > 0 and not any(emp_by_id[i].skill_level != "C" for i in chosen):
                    pools = [home_nocooks + home, cross_nocooks + cross]
                    for pool in pools:
                        for e in pool:
                            if getattr(e, "skill_level", "") != "C" and e.id not in already:
                                chosen.append(e.id)
                                already.add(e.id)
                                weekly_shifts[e.id] += 1
                                need -= 1
                                break
                        if need <= 0:
                            break

            # 3) 그래도 부족하면 유형 무시하고 채우기(홈 우선 → 크로스)
            if need > 0:
                filler = [e for e in home + cross if e.id not in already]
                random.shuffle(filler)
                for e in filler:
                    chosen.append(e.id)
                    already.add(e.id)
                    weekly_shifts[e.id] += 1
                    need -= 1
                    if need == 0:
                        break

            # 4) 여전히 need > 0 이면 빈 자리 남김(예: 가용 인원 1명)
            return chosen[:2]  # 안전상 절대 2명 넘지 않게

        # A 먼저 채우고, B는 A와 중복 금지
        a_done = choose_for_branch('OS', a_fixed)
        already_assigned.update(a_done)
        b_done = choose_for_branch('HC', b_fixed)

        # 근무 확정
        daily.working['OS'] = a_done
        daily.working['HC'] = b_done

        # ---- 휴무 결정: '달력 주차(일~토) 기준'으로 직원별 주당 휴무 상한 적용 ----
        assigned_ids = set(a_done + b_done)
        off_slots = max(0, len(employees) - len(assigned_ids))   # 오늘 휴무로 표기할 최대 인원 수

        # 오늘 근무에 배정되지 않은 사람 = 휴무 후보
        off_candidates = [e for e in employees if e.id not in assigned_ids]

        # 1순위: 이번 달-주차에서 휴무 횟수가 weekly_off_cap 미만인 사람(덜 쉼 → 우선 휴무)
        # 2순위: 이미 상한 도달/초과(불가피할 때만)
        first_bucket  = [e for e in off_candidates if off_count[(week_idx, e.id)] < weekly_off_cap]
        second_bucket = [e for e in off_candidates if off_count[(week_idx, e.id)] >= weekly_off_cap]

        # 공정하게: 이번 주에 '덜 쉰' 순으로 정렬
        first_bucket.sort(key=lambda e: off_count[(week_idx, e.id)])
        second_bucket.sort(key=lambda e: off_count[(week_idx, e.id)])

        todays_off = []
        take = min(off_slots, len(first_bucket))
        todays_off.extend(e.id for e in first_bucket[:take])

        remain = off_slots - len(todays_off)
        if remain > 0 and second_bucket:
            todays_off.extend(e.id for e in second_bucket[:remain])

        daily.holidays = todays_off

        # 카운트 갱신(달력 주차 기준)
        for emp_id in todays_off:
            off_count[(week_idx, emp_id)] += 1

        schedules[date_str] = daily

    save_schedules(schedules)
    print(f"{days}일간 자동 배정 완료(수동 배정 보존={not overwrite}, 휴업일 스킵, 주차별 휴무 상한={weekly_off_cap})")
