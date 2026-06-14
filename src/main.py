import sys
from PySide6.QtWidgets import QApplication
from chog.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set engine paths (optional)
    window = MainWindow(white_engine_path=None, black_engine_path=None)
    window.show()
    sys.exit(app.exec())