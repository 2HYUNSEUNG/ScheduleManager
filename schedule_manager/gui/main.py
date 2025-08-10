# gui/main.py
from PySide6.QtWidgets import QApplication
from schedule_manager.gui.main_window import MainWindow
import sys

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()