# cli/employee_menu.py
from schedule_manager.data.data_manager import load_employees, save_employees
from schedule_manager.models.employee import Employee
from schedule_manager.utils.input_handler import get_input

def employee_menu():
    while True:
        print("\n[직원 관리]")
        print("1. 직원 목록 보기")
        print("2. 직원 추가")
        print("3. 직원 수정")
        print("4. 직원 삭제")
        print("0. 메인 메뉴로")

        choice = input("선택: ")

        if choice == "1":
            show_employees()
        elif choice == "2":
            add_employee()
        elif choice == "3":
            edit_employee()
        elif choice == "4":
            delete_employee()
        elif choice == "0":
            break
        else:
            print("잘못된 선택입니다.")

def show_employees():
    employees = load_employees()
    print("\n[직원 목록]")
    for emp in employees:
        print(f"{emp.id} | {emp.name} | {emp.role} | {emp.skill_level} | {emp.home_branch}")

def add_employee():
    employees = load_employees()
    new_id = max([emp.id for emp in employees], default=0) + 1
    name = get_input("이름: ")
    role = get_input("직급(사장/매니저/직원): ")
    skill = get_input("숙련도(조리/비조리): ")
    branch = get_input("근무지(옥수/효창): ")

    emp = Employee(new_id, name, role, skill, branch)
    employees.append(emp)
    save_employees(employees)
    print("직원이 추가되었습니다.")

def edit_employee():
    employees = load_employees()
    emp_id = int(get_input("수정할 직원 ID: "))
    emp = next((e for e in employees if e.id == emp_id), None)

    if not emp:
        print("해당 ID의 직원이 없습니다.")
        return

    emp.name = get_input(f"이름({emp.name}): ") or emp.name
    emp.role = get_input(f"직급({emp.role}): ") or emp.role
    emp.skill_level = get_input(f"숙련도({emp.skill_level}): ") or emp.skill_level
    emp.home_branch = get_input(f"근무지({emp.home_branch}): ") or emp.home_branch

    save_employees(employees)
    print("직원 정보가 수정되었습니다.")

def delete_employee():
    employees = load_employees()
    emp_id = int(get_input("삭제할 직원 ID: "))
    employees = [e for e in employees if e.id != emp_id]
    save_employees(employees)
    print("직원이 삭제되었습니다.")
