from schedule_manager.exceptions import CancelAction, GoBackAction

def get_input(prompt: str, allow_empty: bool = False):
    while True:
        user_input = input(prompt).strip()

        if user_input.lower() in ["취소", "cancel"]:
            raise CancelAction()
        elif user_input.lower() in ["뒤로", "back"]:
            raise GoBackAction()
        elif user_input.lower() in ["종료", "exit"]:
            raise SystemExit

        if not user_input and not allow_empty:
            print("값을 입력하세요.")
            continue

        return user_input


