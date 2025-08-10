# cli/menu.py
from schedule_manager.cli.employee_menu import employee_menu
from schedule_manager.cli.schedule_menu import (
    schedule_menu, show_schedule,
    employee_work_schedule_menu,
    employee_off_schedule_menu
)
from schedule_manager.logic.scheduler import auto_assign
from schedule_manager.utils.input_handler import get_input
from schedule_manager.exceptions import CancelAction, GoBackAction

def main_menu():
    while True:
        print("\n[근무/휴무 스케줄 관리]")
        print("1. 직원 관리")
        print("2. 일정 관리")
        print("3. 자동 스케줄 배정")
        print("4. 스케줄 보기")
        print("5. 직원별 근무만 보기")
        print("6. 직원별 휴무만 보기")
        print("0. 종료")

        try:
            choice = get_input("선택")
            if choice == "1":
                employee_menu()
            elif choice == "2":
                schedule_menu()
            elif choice == "3":
                start_date = get_input("시작 날짜(YYYY-MM-DD)")
                days = int(get_input("배정 일수"))
                auto_assign(start_date, days)
            elif choice == "4":
                show_schedule()
            elif choice == "5":
                employee_work_schedule_menu()   # ← 근무만
            elif choice == "6":
                employee_off_schedule_menu()    # ← 휴무만
            elif choice == "0":
                print("프로그램을 종료합니다.")
                break
            else:
                print("잘못된 선택.")
        except GoBackAction:
            print("이전 메뉴로 이동")
        except CancelAction:
            print("메인 메뉴로 이동")
