# utils/date_helper.py
import calendar
from datetime import date

def month_week_index_map(year: int, month: int) -> dict[str, int]:
    """
    해당 월의 모든 날짜(YYYY-MM-DD) → 주차 index(1..N) 매핑을 만든다.
    - 주간 기준: 일요일 시작(일~토)
    - monthdatescalendar로 나온 주 중 월이 아닌 날짜는 무시
    - 예: 2025-08은
        week1: 08-01(금)~08-02(토)
        week2: 08-03(일)~08-09(토)
        week3: 08-10~08-16
        week4: 08-17~08-23
        week5: 08-24~08-30
        week6: 08-31(일)  ← 월 경계 내에선 하루짜리 주도 인정
    """
    cal = calendar.Calendar(firstweekday=6)  # 6: Sunday
    weeks = cal.monthdatescalendar(year, month)  # list[list[date]] (7일)
    idx = 0
    result = {}
    for w in weeks:
        # 이 주에 '해당 월'에 속하는 날짜가 하나라도 있으면 주차로 센다
        in_month = [d for d in w if d.month == month]
        if not in_month:
            continue
        idx += 1
        for d in in_month:
            result[d.strftime("%Y-%m-%d")] = idx
    return result
