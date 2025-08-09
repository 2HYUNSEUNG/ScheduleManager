# cli/schedule_menu.py
from schedule_manager.data.data_manager import load_schedules, save_schedules, load_employees
from schedule_manager.models.schedule import DailySchedule
from schedule_manager.utils.input_handler import get_input

def schedule_menu():
    while True:
        print("\n[일정 관리]")
        print("1. 일정 보기")
        print("2. 일정 추가/수정")
        print("3. 휴업 설정")
        print("0. 메인 메뉴로")

        choice = input("선택: ")

        if choice == "1":
            show_schedule()
        elif choice == "2":
            add_or_edit_schedule()
        elif choice == "3":
            close_day()
        elif choice == "0":
            break
        else:
            print("잘못된 선택입니다.")

def show_schedule():
    schedules = load_schedules()
    for date, sch in sorted(schedules.items()):
        print(f"{date} | A: {sch.working['A']} | B: {sch.working['B']} | 휴무: {sch.holidays} | 메모: {sch.memo} | 휴업: {sch.closed}")

def add_or_edit_schedule():
    schedules = load_schedules()
    employees = load_employees()
    date = get_input("날짜(YYYY-MM-DD): ")

    if date not in schedules:
        schedules[date] = DailySchedule(date)

    # 근무자 배정
    print("근무자 ID 입력 (쉼표로 구분)")
    schedules[date].working['A'] = list(map(int, get_input("A: ").split(',')))
    schedules[date].working['B'] = list(map(int, get_input("B: ").split(',')))

    # 휴무자 배정
    schedules[date].holidays = list(map(int, get_input("휴무자 ID: ").split(',')))

    # 메모
    schedules[date].memo = get_input("메모: ")

    save_schedules(schedules)
    print("일정이 저장되었습니다.")

def close_day():
    schedules = load_schedules()
    date = get_input("휴업 날짜(YYYY-MM-DD): ")
    if date not in schedules:
        schedules[date] = DailySchedule(date)
    schedules[date].closed = True
    save_schedules(schedules)
    print(f"{date} 휴업 처리 완료")
