# utils/input_handler.py
from schedule_manager.exceptions import CancelAction, GoBackAction

def get_input(prompt: str, allow_empty: bool = False, default: str | None = None) -> str:
    label = prompt
    if default is not None:
        label += f" [{default}]"
    label += ": "

    while True:
        v = input(label).strip()

        low = v.lower()
        if low in ("취소", "cancel"):
            raise CancelAction()
        if low in ("뒤로", "back"):
            raise GoBackAction()

        if not v and allow_empty:
            return ""   # 명시적 빈값 허용
        if not v:
            print("값을 입력하거나 '취소/뒤로'를 입력하세요.")
            continue
        return v