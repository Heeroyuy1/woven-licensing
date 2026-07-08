"""
Stratum — AI Trading Strategy Analyzer
Desktop Application Entry Point

A professional Windows desktop application for backtesting trading strategies,
AI-powered analysis, parameter optimization, and reporting.
"""
import sys
import os
import logging
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.logger import setup_logger
from ui.main_window import MainWindow

logger = logging.getLogger("Stratum")


def main():
    """Launch the Stratum desktop application."""
    _logger = setup_logger(level=logging.INFO)
    logger.info("Starting Stratum v1.0.0")

    app = QApplication(sys.argv)
    app.setApplicationName("Stratum")
    app.setOrganizationName("Woven Model")

    # Dark theme stylesheet
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #0c1929;
            color: #e8edf2;
            font-family: 'Segoe UI', 'Inter', sans-serif;
        }
        QPushButton {
            background-color: #0891b2;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 600;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #0aa3c7;
        }
        QPushButton:pressed {
            background-color: #067a98;
        }
        QPushButton:disabled {
            background-color: #1e3754;
            color: #5c7b99;
        }
        QPushButton#danger {
            background-color: #dc2626;
        }
        QPushButton#danger:hover {
            background-color: #ef4444;
        }
        QPushButton#secondary {
            background-color: #1e3754;
        }
        QPushButton#secondary:hover {
            background-color: #2a4a6e;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
            background-color: #142235;
            color: #e8edf2;
            border: 1px solid #1e3754;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
            border-color: #0891b2;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 8px;
        }
        QComboBox QAbstractItemView {
            background-color: #142235;
            color: #e8edf2;
            selection-background-color: #0891b2;
            border: 1px solid #1e3754;
        }
        QCheckBox {
            color: #e8edf2;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 3px;
            border: 2px solid #1e3754;
            background-color: #142235;
        }
        QCheckBox::indicator:checked {
            background-color: #0891b2;
            border-color: #0891b2;
        }
        QTabWidget::pane {
            border: 1px solid #1e3754;
            border-radius: 8px;
            background-color: #0c1929;
        }
        QTabBar::tab {
            background-color: #142235;
            color: #8ba4bc;
            border: none;
            padding: 10px 20px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            font-weight: 600;
        }
        QTabBar::tab:selected {
            background-color: #0891b2;
            color: white;
        }
        QTabBar::tab:hover:!selected {
            background-color: #1e3754;
        }
        QTableWidget, QTableView {
            background-color: #142235;
            color: #e8edf2;
            border: 1px solid #1e3754;
            border-radius: 6px;
            gridline-color: #1e3754;
            selection-background-color: #0891b240;
        }
        QHeaderView::section {
            background-color: #0f172a;
            color: #8ba4bc;
            padding: 8px;
            border: none;
            border-bottom: 2px solid #0891b240;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }
        QScrollBar:vertical {
            background-color: #0c1929;
            width: 10px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background-color: #1e3754;
            border-radius: 5px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #2a4a6e;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QProgressBar {
            background-color: #142235;
            border: 1px solid #1e3754;
            border-radius: 6px;
            text-align: center;
            color: #e8edf2;
            font-size: 12px;
        }
        QProgressBar::chunk {
            background-color: #0891b2;
            border-radius: 5px;
        }
        QPlainTextEdit, QTextEdit {
            background-color: #0a0f1c;
            color: #e8edf2;
            border: 1px solid #1e3754;
            border-radius: 6px;
            font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
            font-size: 12px;
        }
        QGroupBox {
            border: 1px solid #1e3754;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #0891b2;
        }
        QSplitter::handle {
            background-color: #1e3754;
        }
        QMenuBar {
            background-color: #0f172a;
            color: #e8edf2;
            border-bottom: 1px solid #1e3754;
        }
        QMenuBar::item:selected {
            background-color: #0891b2;
        }
        QMenu {
            background-color: #142235;
            color: #e8edf2;
            border: 1px solid #1e3754;
        }
        QMenu::item:selected {
            background-color: #0891b2;
        }
        QLabel#section-title {
            font-size: 20px;
            font-weight: 700;
            color: #e8edf2;
            padding: 4px 0;
            border-bottom: 2px solid #0891b240;
        }
        QLabel#positive {
            color: #059669;
            font-weight: 600;
        }
        QLabel#negative {
            color: #dc2626;
            font-weight: 600;
        }
        QLabel#kpi-value {
            font-size: 28px;
            font-weight: 800;
            color: #0891b2;
        }
        QLabel#kpi-label {
            font-size: 11px;
            color: #5c7b99;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
    """)

    window = MainWindow()
    window.show()

    try:
        sys.exit(app.exec())
    except SystemExit:
        pass


if __name__ == "__main__":
    main()
