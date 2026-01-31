# -*- coding: utf-8 -*-
"""
Created on Fri Dec 19 22:17:51 2025

@author: Lucas
"""

# =============================================================
# main.py
# Lanza la GUI principal
# =============================================================

import sys
from PyQt5.QtWidgets import QApplication
from oct_gui import OCTGUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = OCTGUI()
    win.show()
    sys.exit(app.exec_())
