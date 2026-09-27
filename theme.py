"""
theme.py — Dual-Theme QSS Stylesheets (Tactical Dark & Daylight Light).
"""

DARK_STYLE = """
/* ================= GLOBAL STYLES (DARK - DRIVER STATION PRO) ================= */
QMainWindow { background-color: #0F1117; }
QWidget { background-color: #0F1117; color: #E2E8F0; font-family: "SF Pro Display", "Segoe UI", "Inter", sans-serif; font-size: 13px; }
QWidget:disabled { color: #475569; }

QFrame { background-color: #171C28; border: 1px solid #293548; border-radius: 14px; }
QFrame#cardHeader { background-color: #1F2636; border: none; border-bottom: 1px solid #293548; border-top-left-radius: 14px; border-top-right-radius: 14px; }

QLabel { background: transparent; color: #E2E8F0; border: none; }
QLabel#panelTitle { font-size: 12px; font-weight: 800; letter-spacing: 1.5px; color: #35CFFF; font-family: "Segoe UI", sans-serif; }
QLabel#fieldCaption { font-size: 11px; font-weight: 700; color: #7E8B9B; letter-spacing: 0.8px; }

QLabel#statusCard { background-color: #1F2636; border: 1px solid #293548; border-radius: 10px; padding: 8px 12px; font-size: 12px; font-weight: 600; color: #94A3B8; }
QLabel#statusCard:hover { border: 1px solid #35CFFF; background-color: #273145; color: #FFFFFF; }
QLabel#statusCardActive { background-color: rgba(0, 230, 118, 0.08); border: 1px solid rgba(0, 230, 118, 0.35); border-radius: 10px; padding: 8px 12px; font-size: 12px; font-weight: 700; color: #00E676; }
QLabel#statusCardActive:hover { border: 1px solid #00E676; background-color: rgba(0, 230, 118, 0.15); }
QLabel#speedValueLabel { font-size: 26px; font-weight: 800; color: #35CFFF; font-family: "Consolas", "IBM Plex Mono", monospace; }

QLineEdit { background-color: #111520; border: 1px solid #293548; border-radius: 8px; padding: 6px 12px; color: #F8FAFC; font-family: "Consolas", monospace; }
QLineEdit:focus { border: 1px solid #35CFFF; background-color: #171C28; }

QComboBox { background-color: #111520; border: 1px solid #293548; border-radius: 8px; padding: 6px 12px; color: #F8FAFC; }
QComboBox:hover { border: 1px solid #35CFFF; }
QComboBox QAbstractItemView { background-color: #171C28; border: 1px solid #293548; color: #F8FAFC; selection-background-color: #1E40AF; }

QSlider::groove:horizontal { background: #111520; height: 8px; border-radius: 4px; border: 1px solid #293548; }
QSlider::sub-page:horizontal { background: linear-gradient(90deg, #0284C7, #35CFFF); height: 8px; border-radius: 4px; }
QSlider::handle:horizontal { background: #35CFFF; width: 20px; height: 20px; margin: -6px 0; border-radius: 10px; border: 2px solid #0F1117; }
QSlider::handle:horizontal:hover { background: #38BDF8; border: 2px solid #35CFFF; }

QPushButton { background-color: #105E82; color: #FFFFFF; border: 1px solid #1E7B9E; border-radius: 8px; padding: 8px 14px; font-weight: 700; letter-spacing: 0.5px; }
QPushButton:hover { background-color: #0284C7; border: 1px solid #35CFFF; }
QPushButton:pressed { background-color: #0369A1; }

QPushButton#connectButton { background-color: #047857; border: 1px solid #10B981; }
QPushButton#connectButton:hover { background-color: #059669; }
QPushButton#connectButton[connected="true"] { background-color: #B91C1C; border: 1px solid #EF4444; }

QPushButton#btConnectButton { background-color: #105E82; border: 1px solid #35CFFF; }
QPushButton#btConnectButton:hover { background-color: #0284C7; }
QPushButton#btConnectButton[connected="true"] { background-color: #B91C1C; border: 1px solid #EF4444; }

QPushButton#smallButton { background-color: #1F2636; color: #94A3B8; border: 1px solid #293548; }
QPushButton#smallButton:hover { background-color: #2A344A; color: #35CFFF; border: 1px solid #35CFFF; }

QPushButton#presetButton { background-color: #1F2636; color: #35CFFF; border: 1px solid #293548; border-radius: 8px; font-size: 10px; font-weight: 700; padding: 6px 2px; text-align: center; }
QPushButton#presetButton:hover { background-color: #2A344A; border: 1px solid #35CFFF; }
QPushButton#presetButton[active="true"] { background-color: #0284C7; color: #FFFFFF; border: 1px solid #35CFFF; }

QPushButton#dirButton { background-color: #1F2636; border: 1px solid #293548; border-radius: 12px; font-size: 24px; color: #35CFFF; font-weight: bold; }
QPushButton#dirButton:hover { background-color: #2A344A; border: 1px solid #35CFFF; color: #FFFFFF; }
QPushButton#dirButton:pressed, QPushButton#dirButton[active="true"] { background-color: #0284C7; border: 1px solid #35CFFF; color: #FFFFFF; }

QPushButton#dirButtonStop { background-color: #2A1D24; border: 1px solid #6B21A8; border-radius: 12px; font-size: 18px; color: #F43F5E; font-weight: bold; }
QPushButton#dirButtonStop:hover { background-color: #4C1D24; border: 1px solid #F43F5E; color: #FFFFFF; }
QPushButton#dirButtonStop:pressed, QPushButton#dirButtonStop[active="true"] { background-color: #BE123C; border: 1px solid #FF3B30; color: #FFFFFF; }

QPushButton#emergencyButton { background: #FF3B30; color: #FFFFFF; font-size: 15px; font-weight: 900; border-radius: 10px; border: 1px solid #FF6B6B; letter-spacing: 1px; }
QPushButton#emergencyButton:hover { background: #E0241B; border: 1px solid #FFA8A8; }
QPushButton#emergencyButton:pressed { background: #991B1B; }

QLabel#cameraFeed { background-color: #0A0C10; color: #475569; font-size: 18px; font-weight: 700; border: 1px solid #293548; border-radius: 10px; }
QTextEdit#systemConsole { background-color: #0A0C10; border: 1px solid #293548; border-radius: 8px; padding: 8px; font-family: "Consolas", "IBM Plex Mono", monospace; font-size: 11px; color: #94A3B8; }

/* Custom High-Visibility Scrollbar */
QScrollBar:vertical { background: #111520; width: 12px; border-radius: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #293548; min-height: 28px; border-radius: 6px; border: 1px solid #35CFFF; }
QScrollBar::handle:vertical:hover { background: #35CFFF; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal { background: #111520; height: 12px; border-radius: 6px; margin: 0; }
QScrollBar::handle:horizontal { background: #293548; min-width: 28px; border-radius: 6px; border: 1px solid #35CFFF; }
QScrollBar::handle:horizontal:hover { background: #35CFFF; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""

LIGHT_STYLE = """
/* ================= GLOBAL STYLES (LIGHT) ================= */
QMainWindow { background-color: #F1F5F9; }
QWidget { background-color: #F1F5F9; color: #0F172A; font-family: "Segoe UI", sans-serif; font-size: 13px; }
QWidget:disabled { color: #94A3B8; }

QFrame { background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px; }
QFrame#cardHeader { background-color: #F8FAFC; border: none; border-bottom: 1px solid #E2E8F0; border-top-left-radius: 14px; border-top-right-radius: 14px; }

QLabel { background: transparent; color: #0F172A; border: none; }
QLabel#panelTitle { font-size: 12px; font-weight: 800; letter-spacing: 1.5px; color: #0284C7; }
QLabel#fieldCaption { font-size: 11px; font-weight: 700; color: #475569; letter-spacing: 0.8px; }

QLabel#statusCard { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 8px 12px; font-size: 12px; font-weight: 600; color: #334155; }
QLabel#statusCardActive { background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 10px; padding: 8px 12px; font-size: 12px; font-weight: 700; color: #047857; }
QLabel#speedValueLabel { font-size: 26px; font-weight: 800; color: #0284C7; font-family: "Consolas", monospace; }

QLineEdit { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px 12px; color: #0F172A; font-family: "Consolas", monospace; }
QLineEdit:focus { border: 1px solid #0284C7; }

QComboBox { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px 12px; color: #0F172A; }
QComboBox:hover { border: 1px solid #0284C7; }
QComboBox QAbstractItemView { background-color: #FFFFFF; border: 1px solid #CBD5E1; color: #0F172A; selection-background-color: #0284C7; selection-color: #FFFFFF; }

QSlider::groove:horizontal { background: #E2E8F0; height: 8px; border-radius: 4px; }
QSlider::sub-page:horizontal { background: #0284C7; height: 8px; border-radius: 4px; }
QSlider::handle:horizontal { background: #0284C7; width: 20px; height: 20px; margin: -6px 0; border-radius: 10px; }

QPushButton { background-color: #0284C7; color: #FFFFFF; border: none; border-radius: 8px; padding: 8px 14px; font-weight: 700; }
QPushButton:hover { background-color: #0369A1; }
QPushButton:pressed { background-color: #075985; }

QPushButton#connectButton { background-color: #059669; }
QPushButton#connectButton[connected="true"] { background-color: #DC2626; }
QPushButton#btConnectButton { background-color: #0284C7; }
QPushButton#btConnectButton[connected="true"] { background-color: #DC2626; }
QPushButton#smallButton { background-color: #F8FAFC; color: #475569; border: 1px solid #CBD5E1; }
QPushButton#presetButton { background-color: #F8FAFC; color: #0284C7; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 10px; font-weight: 700; padding: 6px 2px; text-align: center; }
QPushButton#presetButton:hover { background-color: #0284C7; color: #FFFFFF; }

QPushButton#dirButton { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 12px; font-size: 24px; color: #0284C7; }
QPushButton#dirButton:hover { background-color: #E0F2FE; border: 1px solid #0284C7; }
QPushButton#dirButton:pressed, QPushButton#dirButton[active="true"] { background-color: #0284C7; color: #FFFFFF; }

QPushButton#dirButtonStop { background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 12px; font-size: 18px; color: #DC2626; }
QPushButton#dirButtonStop:hover { background-color: #FEE2E2; border: 1px solid #DC2626; }
QPushButton#dirButtonStop:pressed, QPushButton#dirButtonStop[active="true"] { background-color: #DC2626; color: #FFFFFF; }

QPushButton#emergencyButton { background: #DC2626; color: #FFFFFF; font-size: 15px; font-weight: 800; border-radius: 10px; }
QPushButton#emergencyButton:hover { background: #EF4444; }

QLabel#cameraFeed { background-color: #0F172A; color: #64748B; font-size: 18px; font-weight: 700; border: 1px solid #CBD5E1; border-radius: 10px; }
QTextEdit#systemConsole { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 8px; font-family: "Consolas", monospace; font-size: 11px; color: #0F172A; }

QScrollBar:vertical { background: #E2E8F0; width: 12px; border-radius: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #CBD5E1; min-height: 28px; border-radius: 6px; border: 1px solid #0284C7; }
QScrollBar::handle:vertical:hover { background: #0284C7; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal { background: #E2E8F0; height: 12px; border-radius: 6px; margin: 0; }
QScrollBar::handle:horizontal { background: #CBD5E1; min-width: 28px; border-radius: 6px; border: 1px solid #0284C7; }
QScrollBar::handle:horizontal:hover { background: #0284C7; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""

STYLE = DARK_STYLE