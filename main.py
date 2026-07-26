import sys
import os
from PySide6.QtWidgets import QApplication
from main_window import MainWindow

import ctypes

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    # Set Windows AppUserModelID so taskbar displays custom icon instead of generic Python python.exe icon
    try:
        myappid = 'aravindnc.musiccleaner.songreviewer.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("MusicCleaner")
    
    icon_path = resource_path("app_icon.ico")
    if os.path.exists(icon_path):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
