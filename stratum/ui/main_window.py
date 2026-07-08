"""Main Window — The primary desktop application window with all tabs."""
import logging
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
import threading

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QGroupBox, QGridLayout, QFormLayout,
    QProgressBar, QPlainTextEdit, QMessageBox, QApplication,
    QCheckBox, QFileDialog, QDateEdit, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QSizePolicy, QMenuBar, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, QDate, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QAction, QFont, QColor, QIcon, QTextCursor, QPixmap

from core.config_manager import ConfigManager, StrategyParams
from core.data_loader import DataLoader
from core.strategy_engine import StrategyEngine
from core.broker import PaperBroker
from core.optimizer import Optimizer
from core.ai_analysis import AIAnalysis
from core.reporting import ReportingEngine
from core.licensing import LicenseManager, FEATURES
from core.logger import get_ui_handler

logger = logging.getLogger("Stratum.UI")


class LicenseDialog(QDialog):
    """License activation dialog shown on first launch."""

    def __init__(self, license_manager: LicenseManager):
        super().__init__()
        self.license_manager = license_manager
        self.activated = False
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Stratum — License Activation")
        self.setFixedSize(500, 400)
        layout = QVBoxLayout()
        layout.setSpacing(16)

        # Header
        header = QLabel("Stratum")
        header.setStyleSheet("font-size: 32px; font-weight: 800; color: #0891b2;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        subtitle = QLabel("AI Trading Strategy Analyzer")
        subtitle.setStyleSheet("font-size: 14px; color: #8ba4bc;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # Trial button
        trial_btn = QPushButton("Start 24-Hour Free Trial")
        trial_btn.clicked.connect(self._start_trial)
        layout.addWidget(trial_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1e3754; max-height: 1px;")
        layout.addWidget(sep)

        # License key input
        layout.addWidget(QLabel("Enter License Key:"))
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX")
        self.key_input.setStyleSheet("font-family: monospace; font-size: 16px; letter-spacing: 4px;")
        layout.addWidget(self.key_input)

        activate_btn = QPushButton("Activate License")
        activate_btn.clicked.connect(self._do_activate)
        layout.addWidget(activate_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #f59e0b;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.setLayout(layout)

    def _start_trial(self):
        success, msg = self.license_manager.check_license()
        if success:
            self.activated = True
            self.close()
        else:
            self.status_label.setText(msg)

    def _do_activate(self):
        key = self.key_input.text().strip()
        if not key:
            self.status_label.setText("Please enter a license key.")
            return
        success, msg = self.license_manager.activate(key)
        self.status_label.setText(msg)
        if success:
            QTimer.singleShot(500, self.close)
            self.activated = True


class BacktestWorker(QObject):
    """Worker thread for running backtests without blocking UI."""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str, int, int)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, symbols: List[str], config: ConfigManager):
        super().__init__()
        self.symbols = symbols
        self.config = config

    def run(self):
        try:
            loader = DataLoader(
                progress_callback=lambda i, t: self.progress.emit("data", i, t)
            )
            engine = StrategyEngine(self.config)
            engine.set_progress_callback(
                lambda sym, idx, total: self.progress.emit(sym, idx, total)
            )

            self.log.emit(f"Fetching data for {len(self.symbols)} symbols...")
            data = loader.fetch_batch(
                symbols=self.symbols,
                start_date=self.config.config.get("start_date", "2020-01-01"),
                end_date=self.config.config.get("end_date", "2025-12-31"),
                interval=self.config.config.get("interval", "1d"),
            )

            if not data:
                self.error.emit("No data loaded. Check symbols/date range.")
                return

            loaded = [f"{s}({len(d)} bars)" for s, d in data.items()]
            self.log.emit(f"Data loaded: {', '.join(loaded)}")

            self.log.emit("Running backtest...")
            results = engine.run_batch(data)

            self.log.emit("Running AI analysis...")
            ai = AIAnalysis()
            ai_result = ai.analyze(results)

            self.log.emit("Analysis complete.")
            self.finished.emit({"results": results, "ai_analysis": ai_result})

        except Exception as e:
            self.error.emit(str(e))
            logger.exception("Backtest failed")


class OptimizeWorker(QObject):
    """Worker for running optimization without blocking UI."""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, symbols: List[str], config: ConfigManager):
        super().__init__()
        self.symbols = symbols
        self.config = config

    def run(self):
        try:
            loader = DataLoader()
            engine = StrategyEngine(self.config)
            optimizer = Optimizer(self.config)

            all_results = {}
            for sym in self.symbols:
                self.progress.emit(f"Optimizing {sym}...")
                sym_df = loader.fetch_symbol(
                    sym,
                    start_date=self.config.config.get("start_date", "2020-01-01"),
                    end_date=self.config.config.get("end_date", "2025-12-31"),
                )
                if sym_df.empty:
                    self.progress.emit(f"No data for {sym}, skipping")
                    continue

                results = optimizer.optimize(
                    engine_callable=lambda s, p, _df=sym_df: engine.run_symbol(s, _df, p),
                    symbol=sym,
                )
                if results:
                    best = results[0]
                    all_results[sym] = {
                        "best_params": best.params,
                        "best_score": best.score,
                        "best_return": best.total_return_pct,
                        "best_sharpe": best.sharpe_ratio,
                        "best_dd": best.max_drawdown_pct,
                        "best_win_rate": best.win_rate,
                        "trades": best.total_trades,
                        "total_results": len(results),
                    }
                    self.progress.emit(f"  {sym} best: score={best.score:.2f}, return={best.total_return_pct:.2f}%")

            self.finished.emit(all_results)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Primary application window with navigation tabs."""

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.license_manager = LicenseManager()
        self.results: Dict = {}
        self.ai_analysis: Optional[Dict] = None
        self.optimization_results: Dict = {}
        self._setup_ui()

        # Check license, show dialog if needed
        lic_ok, lic_msg = self.license_manager.check_license()
        if not lic_ok:
            dialog = LicenseDialog(self.license_manager)
            dialog.exec()
            if not dialog.activated:
                # Re-check after trial initiation
                lic_ok, lic_msg = self.license_manager.check_license()
                if not lic_ok:
                    QMessageBox.critical(self, "License Error", lic_msg)
                    sys.exit(1)

        self._update_license_status(lic_msg)
        self._load_config()
        self.log(f"Stratum initialized. {lic_msg}")

    def _setup_ui(self):
        self.setWindowTitle("Stratum — AI Trading Strategy Analyzer")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #0b1a2e; border-bottom: 2px solid #0891b240;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)

        # Woven Model brand logo icon (matching wovenmodel.com)
        logo_icon = QLabel()
        logo_icon.setFixedSize(36, 36)
        assets_path = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
        if assets_path.exists():
            pixmap = QPixmap(str(assets_path))
            logo_icon.setPixmap(pixmap.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            logo_icon.setStyleSheet("border-radius: 8px;")
        else:
            logo_icon.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #22d3ee, stop:1 #0891b2); "
                "border-radius: 8px; font-size: 14px; font-weight: 800; color: #0a0f1e;"
            )
            logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_icon.setText("WM")
        header_layout.addWidget(logo_icon)

        brand_col = QWidget()
        brand_layout = QVBoxLayout(brand_col)
        brand_layout.setContentsMargins(4, 0, 0, 0)
        brand_layout.setSpacing(0)

        brand_title = QLabel("Woven Model")
        brand_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #e8edf2; letter-spacing: -0.02em;")
        brand_layout.addWidget(brand_title)

        brand_tagline = QLabel("Stratum — AI Trading Strategy Analyzer")
        brand_tagline.setStyleSheet("font-size: 11px; color: #5c7b99;")
        brand_layout.addWidget(brand_tagline)

        header_layout.addWidget(brand_col)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("background-color: #1e3754; max-width: 1px; margin: 4px 12px;")
        header_layout.addWidget(separator)

        header_layout.addStretch()

        self.license_label = QLabel("")
        self.license_label.setStyleSheet("color: #5c7b99; font-size: 11px;")
        header_layout.addWidget(self.license_label)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #8ba4bc; font-size: 12px; padding: 0 12px;")
        header_layout.addWidget(self.status_label)

        main_layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        main_layout.addWidget(self.tabs)

        # Create tabs
        self._setup_dashboard_tab()
        self._setup_backtest_tab()
        self._setup_analysis_tab()
        self._setup_optimization_tab()
        self._setup_config_tab()
        self._setup_watchlist_tab()
        self._setup_reports_tab()
        self._setup_license_tab()
        self._setup_settings_tab()

        # Status bar
        status_bar = QWidget()
        status_bar.setStyleSheet("background-color: #0f172a; border-top: 1px solid #1e3754;")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(12, 4, 12, 4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setVisible(False)
        sb_layout.addWidget(self.progress_bar)

        sb_layout.addStretch()

        self.log_output = QPlainTextEdit()
        self.log_output.setMaximumHeight(80)
        self.log_output.setVisible(False)
        self.log_output.setReadOnly(True)
        sb_layout.addWidget(self.log_output, 1)

        self.toggle_log_btn = QPushButton("Log")
        self.toggle_log_btn.setFixedWidth(60)
        self.toggle_log_btn.clicked.connect(self._toggle_log)
        self.toggle_log_btn.setStyleSheet("background-color: #1e3754; font-size: 11px;")
        sb_layout.addWidget(self.toggle_log_btn)

        main_layout.addWidget(status_bar)

        # Connect log handler
        handler = get_ui_handler()
        if handler:
            handler.set_callback(self._on_log_message)

    def _setup_dashboard_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("Dashboard")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # KPI cards
        kpi_grid = QHBoxLayout()
        kpi_grid.setSpacing(12)
        self.kpi_cards = {}
        for label_key in ["Best Return", "Total Trades", "Avg Sharpe", "Win Rate"]:
            card = QWidget()
            card.setStyleSheet("background-color: #142235; border: 1px solid #1e3754; border-radius: 12px;")
            card.setFixedHeight(100)
            cl = QVBoxLayout(card)
            val = QLabel("--")
            val.setObjectName("kpi-value")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(label_key)
            lbl.setObjectName("kpi-label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(val)
            cl.addWidget(lbl)
            self.kpi_cards[label_key] = val
            kpi_grid.addWidget(card)

        layout.addLayout(kpi_grid)

        # Quick actions
        actions_title = QLabel("Quick Actions")
        actions_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e8edf2; margin-top: 8px;")
        layout.addWidget(actions_title)

        actions_layout = QHBoxLayout()
        btn_run = QPushButton("▶  Run Backtest")
        btn_run.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        actions_layout.addWidget(btn_run)

        btn_optimize = QPushButton("⚙  Optimize Parameters")
        btn_optimize.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        actions_layout.addWidget(btn_optimize)

        btn_export = QPushButton("📊  Export Reports")
        btn_export.clicked.connect(lambda: self.tabs.setCurrentIndex(6))
        actions_layout.addWidget(btn_export)

        btn_watchlist = QPushButton("👁  Manage Watchlist")
        btn_watchlist.clicked.connect(lambda: self.tabs.setCurrentIndex(5))
        actions_layout.addWidget(btn_watchlist)

        layout.addLayout(actions_layout)

        # Recent results summary
        summary_title = QLabel("Last Analysis Summary")
        summary_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e8edf2; margin-top: 8px;")
        layout.addWidget(summary_title)

        self.summary_text = QLabel("No analysis run yet. Go to Backtest tab to run your first analysis.")
        self.summary_text.setStyleSheet("color: #8ba4bc; font-size: 13px; padding: 16px; background-color: #142235; border-radius: 8px;")
        self.summary_text.setWordWrap(True)
        layout.addWidget(self.summary_text)

        layout.addStretch()
        scroll.setWidget(container)
        self.tabs.addTab(scroll, "📊 Dashboard")

    def _setup_backtest_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("Backtesting")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # Configuration controls
        config_group = QGroupBox("Run Configuration")
        config_layout = QGridLayout()

        # Symbols
        config_layout.addWidget(QLabel("Symbols (comma-separated):"), 0, 0)
        self.bt_symbols = QLineEdit("AAPL, TSLA, NVDA, GOOGL, AMD")
        self.bt_symbols.setPlaceholderText("e.g., AAPL, TSLA, NVDA")
        config_layout.addWidget(self.bt_symbols, 0, 1)

        # Date range
        config_layout.addWidget(QLabel("Start Date:"), 1, 0)
        self.bt_start = QDateEdit(QDate(2020, 1, 1))
        self.bt_start.setCalendarPopup(True)
        config_layout.addWidget(self.bt_start, 1, 1)

        config_layout.addWidget(QLabel("End Date:"), 2, 0)
        self.bt_end = QDateEdit(QDate(2025, 12, 31))
        self.bt_end.setCalendarPopup(True)
        config_layout.addWidget(self.bt_end, 2, 1)

        # Capital
        config_layout.addWidget(QLabel("Initial Capital ($):"), 3, 0)
        self.bt_capital = QDoubleSpinBox()
        self.bt_capital.setRange(1000, 100_000_000)
        self.bt_capital.setValue(100000)
        self.bt_capital.setSingleStep(10000)
        config_layout.addWidget(self.bt_capital, 3, 1)

        # Allow shorts
        self.bt_shorts = QCheckBox("Allow Short Selling")
        self.bt_shorts.setChecked(True)
        config_layout.addWidget(self.bt_shorts, 4, 1)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Run button
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶  Run Backtest")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet("font-size: 15px; font-weight: 700; padding: 10px 30px;")
        self.run_btn.clicked.connect(self._run_backtest)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Results table
        results_title = QLabel("Results")
        results_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e8edf2; margin-top: 8px;")
        layout.addWidget(results_title)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels([
            "Symbol", "Return %", "Sharpe", "Max DD %", "Win Rate %", "Trades", "P&L", "AI Score"
        ])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.setMinimumHeight(200)
        layout.addWidget(self.result_table)

        layout.addStretch()
        scroll.setWidget(container)
        self.tabs.addTab(scroll, "🔍 Backtest")

    def _setup_analysis_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("AI Analysis")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # Summary
        self.ai_summary = QLabel("Run a backtest first to see AI analysis.")
        self.ai_summary.setStyleSheet("color: #8ba4bc; font-size: 14px; padding: 12px; background-color: #142235; border-radius: 8px;")
        self.ai_summary.setWordWrap(True)
        layout.addWidget(self.ai_summary)

        # Symbol ratings table
        self.ai_table = QTableWidget()
        self.ai_table.setColumnCount(7)
        self.ai_table.setHorizontalHeaderLabels([
            "Symbol", "Score", "Recommendation", "Volatility",
            "Return %", "Sharpe", "Max DD %"
        ])
        self.ai_table.horizontalHeader().setStretchLastSection(True)
        self.ai_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.ai_table)

        # Rankings
        rankings_group = QGroupBox("Rankings")
        rankings_layout = QGridLayout()
        self.rankings_labels = {}
        rank_items = [
            ("Best Overall", "best_overall"),
            ("Best Return", "best_return"),
            ("Best Sharpe", "best_sharpe"),
            ("Lowest Drawdown", "lowest_drawdown"),
            ("Most Stable", "most_stable"),
            ("Most Volatile", "most_volatile"),
        ]
        for i, (label_text, key) in enumerate(rank_items):
            lbl = QLabel(f"{label_text}:")
            lbl.setStyleSheet("color: #8ba4bc;")
            val = QLabel("--")
            val.setStyleSheet("color: #e8edf2;")
            self.rankings_labels[key] = val
            rankings_layout.addWidget(lbl, i, 0)
            rankings_layout.addWidget(val, i, 1)

        rankings_group.setLayout(rankings_layout)
        layout.addWidget(rankings_group)

        layout.addStretch()
        scroll.setWidget(container)
        self.tabs.addTab(scroll, "🤖 AI Analysis")

    def _setup_optimization_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("Parameter Optimization")
        title.setObjectName("section-title")
        layout.addWidget(title)

        desc = QLabel(
            "Grid search across strategy parameters to find the best-performing configuration "
            "for each symbol."
        )
        desc.setStyleSheet("color: #8ba4bc; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Controls
        ctrl_group = QGroupBox("Optimization Settings")
        ctrl_layout = QGridLayout()

        ctrl_layout.addWidget(QLabel("Symbols:"), 0, 0)
        self.opt_symbols = QLineEdit("AAPL, TSLA, NVDA")
        ctrl_layout.addWidget(self.opt_symbols, 0, 1)

        ctrl_layout.addWidget(QLabel("Scoring Metric:"), 1, 0)
        self.opt_metric = QComboBox()
        self.opt_metric.addItems(["composite", "sharpe", "return", "win_rate", "profit_factor"])
        ctrl_layout.addWidget(self.opt_metric, 1, 1)

        ctrl_group.setLayout(ctrl_layout)
        layout.addWidget(ctrl_group)

        run_btn = QPushButton("⚙  Run Optimization")
        run_btn.setMinimumHeight(40)
        run_btn.clicked.connect(self._run_optimization)
        layout.addWidget(run_btn)

        # Results table
        opt_title = QLabel("Optimization Results")
        opt_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e8edf2; margin-top: 8px;")
        layout.addWidget(opt_title)

        self.opt_table = QTableWidget()
        self.opt_table.setColumnCount(8)
        self.opt_table.setHorizontalHeaderLabels([
            "Symbol", "Best Score", "Best Return %", "Best Sharpe",
            "Best DD %", "Win Rate %", "Trades", "Best Params"
        ])
        self.opt_table.horizontalHeader().setStretchLastSection(True)
        self.opt_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.opt_table)

        layout.addStretch()
        scroll.setWidget(container)
        self.tabs.addTab(scroll, "⚙  Optimize")

    def _setup_config_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("Configuration")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # Profile management
        profile_group = QGroupBox("Strategy Profiles")
        profile_layout = QHBoxLayout()

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self._refresh_profiles()
        profile_layout.addWidget(QLabel("Profile:"))
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Save As...")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("New profile name")
        self.profile_name_input.setMaximumWidth(150)
        profile_layout.addWidget(self.profile_name_input)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # Strategy parameters
        params_group = QGroupBox("Strategy Parameters (RSI + SMA)")
        params_layout = QGridLayout()

        params_layout.addWidget(QLabel("SMA Period:"), 0, 0)
        self.cfg_sma = QSpinBox()
        self.cfg_sma.setRange(5, 200)
        self.cfg_sma.setValue(20)
        params_layout.addWidget(self.cfg_sma, 0, 1)

        params_layout.addWidget(QLabel("RSI Period:"), 1, 0)
        self.cfg_rsi_period = QSpinBox()
        self.cfg_rsi_period.setRange(5, 50)
        self.cfg_rsi_period.setValue(14)
        params_layout.addWidget(self.cfg_rsi_period, 1, 1)

        params_layout.addWidget(QLabel("RSI Buy Threshold:"), 2, 0)
        self.cfg_rsi_buy = QDoubleSpinBox()
        self.cfg_rsi_buy.setRange(10, 45)
        self.cfg_rsi_buy.setValue(30)
        params_layout.addWidget(self.cfg_rsi_buy, 2, 1)

        params_layout.addWidget(QLabel("RSI Sell Threshold:"), 3, 0)
        self.cfg_rsi_sell = QDoubleSpinBox()
        self.cfg_rsi_sell.setRange(55, 90)
        self.cfg_rsi_sell.setValue(70)
        params_layout.addWidget(self.cfg_rsi_sell, 3, 1)

        params_layout.addWidget(QLabel("Stop Loss %:"), 4, 0)
        self.cfg_stop_loss = QDoubleSpinBox()
        self.cfg_stop_loss.setRange(0.5, 10)
        self.cfg_stop_loss.setValue(2)
        self.cfg_stop_loss.setSingleStep(0.5)
        params_layout.addWidget(self.cfg_stop_loss, 4, 1)

        params_layout.addWidget(QLabel("Take Profit %:"), 5, 0)
        self.cfg_take_profit = QDoubleSpinBox()
        self.cfg_take_profit.setRange(1, 50)
        self.cfg_take_profit.setValue(5)
        self.cfg_take_profit.setSingleStep(0.5)
        params_layout.addWidget(self.cfg_take_profit, 5, 1)

        params_layout.addWidget(QLabel("Max Holding Bars:"), 6, 0)
        self.cfg_max_holding = QSpinBox()
        self.cfg_max_holding.setRange(1, 50)
        self.cfg_max_holding.setValue(5)
        params_layout.addWidget(self.cfg_max_holding, 6, 1)

        params_layout.addWidget(QLabel("Max Exposure %:"), 7, 0)
        self.cfg_max_exposure = QDoubleSpinBox()
        self.cfg_max_exposure.setRange(1, 50)
        self.cfg_max_exposure.setValue(10)
        params_layout.addWidget(self.cfg_max_exposure, 7, 1)

        params_layout.addWidget(QLabel("Risk % Per Trade:"), 8, 0)
        self.cfg_risk = QDoubleSpinBox()
        self.cfg_risk.setRange(0.1, 5)
        self.cfg_risk.setValue(1)
        self.cfg_risk.setSingleStep(0.1)
        params_layout.addWidget(self.cfg_risk, 8, 1)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        save_cfg_btn = QPushButton("Save Configuration")
        save_cfg_btn.clicked.connect(self._save_config)
        layout.addWidget(save_cfg_btn)

        layout.addStretch()
        scroll.setWidget(container)
        self.tabs.addTab(scroll, "⚙  Config")

    def _setup_watchlist_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("Watchlist & Symbol Manager")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # Add symbol
        add_group = QGroupBox("Add Symbol")
        add_layout = QHBoxLayout()
        self.wl_symbol_input = QLineEdit()
        self.wl_symbol_input.setPlaceholderText("Enter symbol (e.g., AAPL)")
        add_layout.addWidget(self.wl_symbol_input)

        add_btn = QPushButton("Add to Watchlist")
        add_btn.clicked.connect(self._add_watchlist)
        add_layout.addWidget(add_btn)
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        # Watchlist
        self.wl_list = QListWidget()
        self.wl_list.setMinimumHeight(200)
        layout.addWidget(QLabel("Your Watchlist:"))

        # Default symbols
        for sym in ["AAPL", "TSLA", "NVDA", "GOOGL", "AMD", "META", "MSFT", "AMZN"]:
            item = QListWidgetItem(sym)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.wl_list.addItem(item)

        layout.addWidget(self.wl_list)

        btn_layout = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.setObjectName("danger")
        remove_btn.clicked.connect(self._remove_watchlist)
        btn_layout.addWidget(remove_btn)

        analyze_btn = QPushButton("Analyze Watchlist")
        analyze_btn.clicked.connect(self._analyze_watchlist)
        btn_layout.addWidget(analyze_btn)

        layout.addLayout(btn_layout)

        layout.addStretch()
        scroll.setWidget(container)
        self.tabs.addTab(scroll, "👁  Watchlist")

    def _setup_reports_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("Reports & Export")
        title.setObjectName("section-title")
        layout.addWidget(title)

        desc = QLabel("Export backtest results and AI analysis in various formats.")
        desc.setStyleSheet("color: #8ba4bc; font-size: 13px;")
        layout.addWidget(desc)

        # Export buttons
        exports = [
            ("📄  Export as PDF", "pdf", self._export_pdf),
            ("📗  Export as Excel", "xlsx", self._export_excel),
            ("📊  Export as CSV", "csv", self._export_csv),
            ("📋  Export as JSON", "json", self._export_json),
            ("📉  Export Trades CSV", "trades_csv", self._export_trades_csv),
        ]

        for label_text, fmt, callback in exports:
            btn = QPushButton(label_text)
            btn.setMinimumHeight(36)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        self.export_status = QLabel("")
        self.export_status.setStyleSheet("color: #059669; font-size: 13px;")
        layout.addWidget(self.export_status)

        layout.addStretch()
        self.tabs.addTab(container, "📊 Reports")

    def _setup_license_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("License & Activation")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # Status
        self.lic_status = QLabel("Checking license...")
        self.lic_status.setStyleSheet("font-size: 15px; padding: 16px; background-color: #142235; border-radius: 8px;")
        layout.addWidget(self.lic_status)

        # Activate
        activate_group = QGroupBox("Activate License")
        act_layout = QVBoxLayout()

        self.lic_key_input = QLineEdit()
        self.lic_key_input.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX")
        self.lic_key_input.setStyleSheet("font-family: monospace; font-size: 16px; letter-spacing: 4px;")
        act_layout.addWidget(self.lic_key_input)

        act_btn = QPushButton("Activate")
        act_btn.clicked.connect(self._activate_license)
        act_layout.addWidget(act_btn)

        self.lic_msg = QLabel("")
        self.lic_msg.setStyleSheet("color: #f59e0b;")
        act_layout.addWidget(self.lic_msg)

        activate_group.setLayout(act_layout)
        layout.addWidget(activate_group)

        # Deactivate
        deact_btn = QPushButton("Deactivate License")
        deact_btn.setObjectName("danger")
        deact_btn.clicked.connect(self._deactivate_license)
        layout.addWidget(deact_btn)

        # Info
        info_text = QLabel(
            "Licensing Information:\n"
            "• Each license is valid for one machine\n"
            "• Licenses expire 1 year from activation\n"
            "• You can activate on a new machine by deactivating the old one\n"
            "• Trial: 24 hours of full functionality"
        )
        info_text.setStyleSheet("color: #5c7b99; font-size: 12px; padding: 12px;")
        info_text.setWordWrap(True)
        layout.addWidget(info_text)

        layout.addStretch()
        self.tabs.addTab(container, "🔑 License")

    def _setup_settings_tab(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # General settings
        settings_group = QGroupBox("General")
        settings_layout = QGridLayout()

        settings_layout.addWidget(QLabel("Commission per Share ($):"), 0, 0)
        self.set_commission = QDoubleSpinBox()
        self.set_commission.setRange(0, 0.1)
        self.set_commission.setSingleStep(0.001)
        self.set_commission.setValue(0)
        settings_layout.addWidget(self.set_commission, 0, 1)

        settings_layout.addWidget(QLabel("Slippage %:"), 1, 0)
        self.set_slippage = QDoubleSpinBox()
        self.set_slippage.setRange(0, 0.1)
        self.set_slippage.setSingleStep(0.0001)
        self.set_slippage.setDecimals(4)
        self.set_slippage.setValue(0.0005)
        settings_layout.addWidget(self.set_slippage, 1, 1)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Actions
        clear_btn = QPushButton("Clear All Cached Data")
        clear_btn.clicked.connect(self._clear_cache)
        layout.addWidget(clear_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self._reset_defaults)
        layout.addWidget(reset_btn)

        layout.addStretch()
        self.tabs.addTab(container, "⚙  Settings")

    def _load_config(self):
        cfg = self.config.load()
        sp = self.config.get_strategy_params()
        self.cfg_sma.setValue(sp.sma_period)
        self.cfg_rsi_period.setValue(sp.rsi_period)
        self.cfg_rsi_buy.setValue(sp.rsi_buy_threshold)
        self.cfg_rsi_sell.setValue(sp.rsi_sell_threshold)
        self.cfg_stop_loss.setValue(sp.stop_loss_pct * 100)
        self.cfg_take_profit.setValue(sp.take_profit_pct * 100)
        self.cfg_max_holding.setValue(sp.max_holding_bars)
        self.cfg_max_exposure.setValue(sp.max_exposure_pct * 100)
        self.cfg_risk.setValue(sp.risk_pct * 100)
        self.bt_capital.setValue(cfg.get("initial_capital", 100000))
        self.bt_shorts.setChecked(cfg.get("allow_shorts", True))
        self.set_commission.setValue(cfg.get("commission_per_share", 0))
        self.set_slippage.setValue(cfg.get("slippage_pct", 0.0005))
        self.log("Configuration loaded.")

    def _save_config(self):
        sp = StrategyParams(
            sma_period=self.cfg_sma.value(),
            rsi_period=self.cfg_rsi_period.value(),
            rsi_buy_threshold=self.cfg_rsi_buy.value(),
            rsi_sell_threshold=self.cfg_rsi_sell.value(),
            stop_loss_pct=self.cfg_stop_loss.value() / 100,
            take_profit_pct=self.cfg_take_profit.value() / 100,
            max_holding_bars=self.cfg_max_holding.value(),
            max_exposure_pct=self.cfg_max_exposure.value() / 100,
            risk_pct=self.cfg_risk.value() / 100,
        )
        self.config.set_strategy_params(sp)
        self.config.config["initial_capital"] = self.bt_capital.value()
        self.config.config["allow_shorts"] = self.bt_shorts.isChecked()
        self.config.config["commission_per_share"] = self.set_commission.value()
        self.config.config["slippage_pct"] = self.set_slippage.value()
        self.config.save()
        self.log("Configuration saved.")

    def _check_feature(self, feature: str) -> bool:
        """Check if a feature is allowed. Show message if not."""
        allowed, reason = self.license_manager.is_feature_allowed(feature)
        if not allowed:
            msg_title = "License Feature Locked"
            msg_text = f"{reason}\n\nTo unlock all features, enter a valid license key in the License tab or contact jude@wovenmodel.com."
            QMessageBox.information(self, msg_title, msg_text)
            self.log(f"LICENSE: {feature} blocked — {reason}")
        return allowed

    def _run_backtest(self):
        if not self._check_feature("backtest"):
            return

        symbols_text = self.bt_symbols.text().strip()
        if not symbols_text:
            QMessageBox.warning(self, "Input Error", "Enter at least one symbol.")
            return

        symbols = [s.strip().upper() for s in symbols_text.split(",") if s.strip()]

        # Trial limitation: max 2 symbols
        max_symbols = self.license_manager.get_trial_limit("backtest")
        if max_symbols is not None and len(symbols) > max_symbols:
            QMessageBox.information(self, "Trial Limitation",
                f"Trial mode is limited to {max_symbols} symbols at a time.\n\n"
                f"You entered {len(symbols)}. Please reduce to {max_symbols} or enter a license key to unlock unlimited symbols.")
            return
        self.config.config["symbols"] = symbols
        self.config.config["start_date"] = self.bt_start.date().toString("yyyy-MM-dd")
        self.config.config["end_date"] = self.bt_end.date().toString("yyyy-MM-dd")
        self.config.config["initial_capital"] = self.bt_capital.value()
        self.config.config["allow_shorts"] = self.bt_shorts.isChecked()

        self._save_config()
        self._set_busy(True, "Running backtest...")

        self.worker_thread = QThread()
        self.worker = BacktestWorker(symbols, self.config)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_backtest_finished)
        self.worker.error.connect(self._on_backtest_error)
        self.worker.progress.connect(self._on_backtest_progress)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.start()

    def _on_backtest_finished(self, data: Dict):
        self._set_busy(False)
        self.results = data.get("results", {})
        self.ai_analysis = data.get("ai_analysis", {})
        self._update_results_table()
        self._update_ai_analysis()
        self._update_dashboard()
        self.log(f"Backtest complete: {len(self.results)} symbols analyzed.")

    def _on_backtest_error(self, msg: str):
        self._set_busy(False)
        QMessageBox.critical(self, "Backtest Error", msg)
        self.log(f"ERROR: {msg}")

    def _on_backtest_progress(self, stage: str, current: int, total: int):
        if stage == "data":
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.status_label.setText(f"Fetching data... {current}/{total}")
        else:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.status_label.setText(f"Backtesting {stage}... {current}/{total}")

    def _update_results_table(self):
        if not self.results:
            return
        self.result_table.setRowCount(0)
        ai_ratings = (self.ai_analysis or {}).get("symbol_ratings", {})

        sorted_symbols = sorted(self.results.keys())
        self.result_table.setRowCount(len(sorted_symbols))

        for i, sym in enumerate(sorted_symbols):
            result = self.results[sym]
            if "performance" not in result:
                continue
            p = result["performance"]
            rating = ai_ratings.get(sym, {})

            self.result_table.setItem(i, 0, QTableWidgetItem(sym))
            self._set_table_item(i, 1, f"{p.get('total_return_pct', 0):+.2f}%",
                                 p.get('total_return_pct', 0) >= 0)
            self._set_table_item(i, 2, f"{p.get('sharpe_ratio', 0):.2f}")
            self._set_table_item(i, 3, f"{p.get('max_drawdown_pct', 0):.2f}%", False)
            self._set_table_item(i, 4, f"{p.get('win_rate', 0):.1f}%")
            self._set_table_item(i, 5, str(p.get('total_trades', 0)))
            self._set_table_item(i, 6, f"${p.get('total_realized_pnl', 0):,.2f}",
                                 p.get('total_realized_pnl', 0) >= 0)
            self._set_table_item(i, 7, f"{rating.get('overall_score', '--')}")

    def _set_table_item(self, row: int, col: int, text: str, positive: Optional[bool] = None):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if positive is True:
            item.setForeground(QColor("#059669"))
        elif positive is False:
            item.setForeground(QColor("#dc2626"))
        self.result_table.setItem(row, col, item)

    def _update_ai_analysis(self):
        if not self.ai_analysis:
            return
        ratings = self.ai_analysis.get("symbol_ratings", {})
        summary = self.ai_analysis.get("summary", "")
        rankings = self.ai_analysis.get("rankings", {})

        self.ai_summary.setText(summary or "AI analysis available after backtest.")

        # Ratings table
        self.ai_table.setRowCount(0)
        sorted_syms = sorted(ratings.keys(), key=lambda s: ratings[s]["overall_score"], reverse=True)
        self.ai_table.setRowCount(len(sorted_syms))

        for i, sym in enumerate(sorted_syms):
            r = ratings[sym]
            sym_item = QTableWidgetItem(sym)
            sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ai_table.setItem(i, 0, sym_item)

            score_item = QTableWidgetItem(f"{r.get('overall_score', 0):.0f}/100")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            score_item.setForeground(QColor("#059669") if r.get("overall_score", 0) >= 60 else QColor("#dc2626"))
            self.ai_table.setItem(i, 1, score_item)

            code_item = QTableWidgetItem(r.get("recommendation", ""))
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code_item.setForeground(QColor("#059669") if r.get("recommendation", "") == "Recommended to Trade" else QColor("#dc2626"))
            self.ai_table.setItem(i, 2, code_item)

            vol_item = QTableWidgetItem(r.get("volatility", ""))
            vol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ai_table.setItem(i, 3, vol_item)

            ret_item = QTableWidgetItem(f"{r.get('total_return_pct', 0):+.2f}%")
            ret_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ret_item.setForeground(QColor("#059669") if r.get("total_return_pct", 0) >= 0 else QColor("#dc2626"))
            self.ai_table.setItem(i, 4, ret_item)

            shr_item = QTableWidgetItem(f"{r.get('sharpe_ratio', 0):.2f}")
            shr_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ai_table.setItem(i, 5, shr_item)

            dd_item = QTableWidgetItem(f"{r.get('max_drawdown_pct', 0):.2f}%")
            dd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ai_table.setItem(i, 6, dd_item)

        # Rankings
        for key, label_widget in self.rankings_labels.items():
            symbols_list = rankings.get(key, [])
            if symbols_list:
                label_widget.setText(", ".join(symbols_list))

    def _update_dashboard(self):
        if not self.results:
            return
        ratings = (self.ai_analysis or {}).get("symbol_ratings", {})

        total_returns = [p.get("total_return_pct", 0) for r in self.results.values()
                        for p in [r.get("performance", {})] if p]
        total_trades = sum(p.get("total_trades", 0) for r in self.results.values()
                          for p in [r.get("performance", {})] if p)
        avg_sharpe = 0
        win_rates = []
        if total_returns:
            avg_sharpe = sum(p.get("sharpe_ratio", 0) for r in self.results.values()
                            for p in [r.get("performance", {})] if p) / len(total_returns)
            win_rates = [p.get("win_rate", 0) for r in self.results.values()
                        for p in [r.get("performance", {})] if p]

        best_ret = max(total_returns) if total_returns else 0
        avg_wr = sum(win_rates) / len(win_rates) if win_rates else 0

        self.kpi_cards["Best Return"].setText(f"{best_ret:+.1f}%")
        self.kpi_cards["Total Trades"].setText(str(total_trades))
        self.kpi_cards["Avg Sharpe"].setText(f"{avg_sharpe:.2f}")
        self.kpi_cards["Win Rate"].setText(f"{avg_wr:.1f}%")

        # Summary text
        summary_lines = []
        if ratings:
            recs = self.ai_analysis.get("recommendations", {})
            trade = len(recs.get("recommended_to_trade", []))
            caution = len(recs.get("trade_with_caution", []))
            avoid = len(recs.get("avoid_trading", []))
            summary_lines.append(f"Analyzed {len(ratings)} symbols — "
                               f"Recommend: {trade} trade | {caution} caution | {avoid} avoid")

        if total_returns:
            summary_lines.append(f"Return range: {min(total_returns):+.2f}% to {max(total_returns):+.2f}%")
            summary_lines.append(f"Total trades across all symbols: {total_trades}")

        self.summary_text.setText("\n".join(summary_lines) if summary_lines else "No analysis data available.")

    def _run_optimization(self):
        symbols_text = self.opt_symbols.text().strip()
        symbols = [s.strip().upper() for s in symbols_text.split(",") if s.strip()]
        if not symbols:
            QMessageBox.warning(self, "Input Error", "Enter at least one symbol.")
            return

        if "optimization" not in self.config.config:
            self.config.config["optimization"] = {}
        self.config.config["optimization"]["scoring_metric"] = self.opt_metric.currentText()

        self._set_busy(True, "Running optimization...")

        self.opt_thread = QThread()
        self.opt_worker = OptimizeWorker(symbols, self.config)
        self.opt_worker.moveToThread(self.opt_thread)
        self.opt_thread.started.connect(self.opt_worker.run)
        self.opt_worker.finished.connect(self._on_optimization_finished)
        self.opt_worker.error.connect(self._on_backtest_error)
        self.opt_worker.progress.connect(lambda m: self.log(m))
        self.opt_worker.finished.connect(self.opt_thread.quit)
        self.opt_worker.error.connect(self.opt_thread.quit)
        self.opt_thread.start()

    def _on_optimization_finished(self, results: Dict):
        self._set_busy(False)
        self.optimization_results = results
        self._update_optimization_table()
        self.log(f"Optimization complete for {len(results)} symbols.")

    def _update_optimization_table(self):
        if not self.optimization_results:
            return
        self.opt_table.setRowCount(0)
        self.opt_table.setRowCount(len(self.optimization_results))

        for i, (sym, data) in enumerate(sorted(self.optimization_results.items())):
            self.opt_table.setItem(i, 0, QTableWidgetItem(sym))
            self.opt_table.setItem(i, 1, QTableWidgetItem(f"{data.get('best_score', 0):.3f}"))
            self.opt_table.setItem(i, 2, QTableWidgetItem(f"{data.get('best_return', 0):+.2f}%"))
            self.opt_table.setItem(i, 3, QTableWidgetItem(f"{data.get('best_sharpe', 0):.2f}"))
            self.opt_table.setItem(i, 4, QTableWidgetItem(f"{data.get('best_dd', 0):.2f}%"))
            self.opt_table.setItem(i, 5, QTableWidgetItem(f"{data.get('best_win_rate', 0):.1f}%"))
            self.opt_table.setItem(i, 6, QTableWidgetItem(str(data.get('trades', 0))))
            params = data.get("best_params", {})
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            self.opt_table.setItem(i, 7, QTableWidgetItem(param_str))

            for col in range(1, 7):
                self.opt_table.item(i, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _load_profile(self):
        name = self.profile_combo.currentText()
        if name:
            self.config.load(name)
            self._load_config()
            self.log(f"Loaded profile: {name}")

    def _save_profile(self):
        name = self.profile_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Enter a profile name.")
            return
        self._save_config()
        self.config.save(name)
        self._refresh_profiles()
        self.profile_combo.setCurrentText(name)
        self.log(f"Saved profile: {name}")

    def _refresh_profiles(self):
        current = self.profile_combo.currentText()
        self.profile_combo.clear()
        for p in self.config.list_profiles():
            self.profile_combo.addItem(p)
        idx = self.profile_combo.findText(current)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

    def _add_watchlist(self):
        sym = self.wl_symbol_input.text().strip().upper()
        if not sym:
            return
        for i in range(self.wl_list.count()):
            if self.wl_list.item(i).text() == sym:
                return
        item = QListWidgetItem(sym)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self.wl_list.addItem(item)
        self.wl_symbol_input.clear()
        self.log(f"Added {sym} to watchlist")

    def _remove_watchlist(self):
        for item in self.wl_list.selectedItems():
            self.wl_list.takeItem(self.wl_list.row(item))

    def _analyze_watchlist(self):
        symbols = []
        for i in range(self.wl_list.count()):
            item = self.wl_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                symbols.append(item.text())
        if symbols:
            self.bt_symbols.setText(", ".join(symbols))
            self.tabs.setCurrentIndex(1)
            self.log(f"Set {len(symbols)} watchlist symbols for analysis")

    def _export_pdf(self):
        if not self.results:
            self.export_status.setText("No results to export. Run a backtest first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", "stratum_report.pdf", "PDF (*.pdf)")
        if path:
            reporter = ReportingEngine()
            result_path = reporter.export_pdf(self.results, self.ai_analysis, Path(path).name)
            self.export_status.setText(f"Exported PDF: {result_path}")
            self.log(f"PDF exported to {result_path}")

    def _export_excel(self):
        if not self.results:
            self.export_status.setText("No results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", "stratum_results.xlsx", "Excel (*.xlsx)")
        if path:
            reporter = ReportingEngine()
            result_path = reporter.export_excel(self.results, self.ai_analysis, Path(path).name)
            self.export_status.setText(f"Exported Excel: {result_path}")

    def _export_csv(self):
        if not self.results:
            self.export_status.setText("No results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Report", "stratum_results.csv", "CSV (*.csv)")
        if path:
            reporter = ReportingEngine()
            result_path = reporter.export_csv(self.results, Path(path).name)
            self.export_status.setText(f"Exported CSV: {result_path}")

    def _export_json(self):
        if not self.results:
            self.export_status.setText("No results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON Report", "stratum_results.json", "JSON (*.json)")
        if path:
            reporter = ReportingEngine()
            result_path = reporter.export_json(self.results, self.ai_analysis, Path(path).name)
            self.export_status.setText(f"Exported JSON: {result_path}")

    def _export_trades_csv(self):
        if not self.results:
            self.export_status.setText("No results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Trades CSV", "stratum_trades.csv", "CSV (*.csv)")
        if path:
            reporter = ReportingEngine()
            result_path = reporter.export_trades_csv(self.results, Path(path).name)
            self.export_status.setText(f"Exported trades CSV: {result_path}")

    def _activate_license(self):
        key = self.lic_key_input.text().strip()
        if not key:
            self.lic_msg.setText("Enter a license key.")
            return
        success, msg = self.license_manager.activate(key)
        self.lic_msg.setText(msg)
        if success:
            self._update_license_status(msg)

    def _deactivate_license(self):
        self.license_manager.deactivate()
        self._update_license_status("License deactivated.")

    def _update_license_status(self, msg: str):
        self.lic_status.setText(msg)
        self.license_label.setText(msg[:60] + "..." if len(msg) > 60 else msg)

    def _clear_cache(self):
        loader = DataLoader()
        loader.clear_cache()
        self.log("Cache cleared.")

    def _reset_defaults(self):
        self.config.reset_to_defaults()
        self._load_config()
        self.log("Reset to factory defaults.")

    def _toggle_log(self):
        self.log_output.setVisible(not self.log_output.isVisible())

    def _on_log_message(self, msg: str):
        # Thread-safe: queue append on main event loop via QTimer
        QTimer.singleShot(0, lambda m=msg: self.log_output.appendPlainText(m))

    def log(self, msg: str):
        logger.info(msg)
        self.log_output.appendPlainText(
            f"{datetime.now().strftime('%H:%M:%S')} [INFO] {msg}"
        )

    def _set_busy(self, busy: bool, status: str = ""):
        self.run_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)  # indeterminate
            self.status_label.setText(status)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText("Ready")
            QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
