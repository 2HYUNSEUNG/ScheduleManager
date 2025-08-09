# logic/scheduler.py
from schedule_manager.data.data_manager import load_employees, load_schedules, save_schedules
from schedule_manager.models.schedule import DailySchedule
from datetime import datetime, timedelta
import random

def auto_assign(start_date, days=7):
    employees = load_employees()
    schedules = load_schedules()

    # 주간 근무 횟수 기록
    weekly_shifts = {e.id: 0 for e in employees}

    date_obj = datetime.strptime(start_date, "%Y-%m-%d")

    for i in range(days):
        current_date = (date_obj + timedelta(days=i)).strftime("%Y-%m-%d")
        weekday = (date_obj + timedelta(days=i)).weekday()
        daily = DailySchedule(current_date)

        # 오늘 근무 가능 인원 필터링
        available = []
        for e in employees:
            # 고정휴무 체크
            if weekday in e.fixed_holidays:
                continue
            # 신청휴무 체크
            if current_date in e.holiday_requests:
                continue
            # 최대 근무 횟수 초과 방지
            if weekly_shifts[e.id] >= e.max_shifts_per_week:
                continue
            available.append(e)

        # 지점별 배정
        for branch in ['A', 'B']:
            branch_candidates = [e for e in available if e.home_branch == branch]

            # 조리 가능자 최소 1명 필수
            cooks = [e for e in branch_candidates if e.skill_level == 'C']
            nocooks = [e for e in branch_candidates if e.skill_level != 'C']

            # 인원 부족 시 다른 지점 인원 보충
            if len(cooks) < 1 or len(nocooks) < 1:
                cross_branch = [e for e in available if e.home_branch != branch]
                for e in cross_branch:
                    if e.skill_level == 'C' and e not in cooks:
                        cooks.append(e)
                    elif e.skill_level != 'C' and e not in nocooks:
                        nocooks.append(e)

            # 최종 배정 (랜덤)
            if cooks and nocooks:
                chosen = [random.choice(cooks), random.choice(nocooks)]
            else:
                chosen = random.sample(available, 2)

            daily.working[branch] = [emp.id for emp in chosen]

            # 배정된 인원 근무 횟수 증가
            for emp in chosen:
                weekly_shifts[emp.id] += 1

        # 휴무자 계산
        assigned_ids = daily.working['A'] + daily.working['B']
        daily.holidays = [e.id for e in employees if e.id not in assigned_ids]

        schedules[current_date] = daily

    save_schedules(schedules)
    print(f"{days}일간 조건 반영 자동 배정 완료")
