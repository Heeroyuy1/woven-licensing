"""Reporting Engine — Exports results as PDF, Excel, CSV, JSON."""
import json
import logging
import csv
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import os

import pandas as pd
import numpy as np

logger = logging.getLogger("Stratum.Reporting")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


class ReportingEngine:
    """Exports backtest results and AI analysis in multiple formats."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or REPORTS_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, results: Dict, ai_analysis: Optional[Dict] = None, filename: str = "results.json") -> str:
        """Export all results as JSON."""
        path = self.output_dir / filename
        output = {
            "platform": "Stratum",
            "generated_at": datetime.now().isoformat(),
            "results": self._sanitize(results),
        }
        if ai_analysis:
            output["ai_analysis"] = ai_analysis
        with open(path, "w") as f:
            json.dump(output, f, indent=2, default=str)
        logger.info(f"Exported JSON to {path}")
        return str(path)

    def export_csv(self, results: Dict, filename: str = "results.csv") -> str:
        """Export performance summary as CSV."""
        path = self.output_dir / filename
        rows = []
        for sym, result in results.items():
            if "performance" not in result:
                continue
            perf = result["performance"]
            rows.append({
                "symbol": sym,
                "start_date": result.get("start_date", ""),
                "end_date": result.get("end_date", ""),
                "total_return_pct": perf.get("total_return_pct", 0),
                "sharpe_ratio": perf.get("sharpe_ratio", 0),
                "max_drawdown_pct": perf.get("max_drawdown_pct", 0),
                "win_rate": perf.get("win_rate", 0),
                "total_trades": perf.get("total_trades", 0),
                "win_count": perf.get("win_count", 0),
                "loss_count": perf.get("loss_count", 0),
                "total_pnl": perf.get("total_realized_pnl", 0),
                "avg_win": perf.get("avg_win", 0),
                "avg_loss": perf.get("avg_loss", 0),
                "pl_ratio": perf.get("pl_ratio", 0),
                "max_consecutive_wins": perf.get("max_consecutive_wins", 0),
                "max_consecutive_losses": perf.get("max_consecutive_losses", 0),
                "avg_trade_duration_days": perf.get("avg_trade_duration_days", 0),
            })
        if not rows:
            return ""
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False)
        logger.info(f"Exported CSV to {path}")
        return str(path)

    def export_trades_csv(self, results: Dict, filename: str = "trades.csv") -> str:
        """Export all trades across symbols as CSV."""
        path = self.output_dir / filename
        all_trades = []
        for sym, result in results.items():
            trades = result.get("trades", [])
            for t in trades:
                t["symbol"] = sym
                all_trades.append(t)
        if not all_trades:
            return ""
        df = pd.DataFrame(all_trades)
        df.to_csv(path, index=False)
        logger.info(f"Exported trades CSV to {path}")
        return str(path)

    def export_excel(self, results: Dict, ai_analysis: Optional[Dict] = None, filename: str = "results.xlsx") -> str:
        """Export results to multi-sheet Excel workbook."""
        path = self.output_dir / filename
        try:
            import openpyxl
        except ImportError:
            logger.error("openpyxl not installed. pip install openpyxl")
            return ""

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            # Performance summary
            perf_rows = []
            for sym, result in results.items():
                if "performance" not in result:
                    continue
                perf = result["performance"]
                perf_rows.append({
                    "Symbol": sym,
                    "Total Return %": perf.get("total_return_pct", 0),
                    "Sharpe Ratio": perf.get("sharpe_ratio", 0),
                    "Max Drawdown %": perf.get("max_drawdown_pct", 0),
                    "Win Rate %": perf.get("win_rate", 0),
                    "Total Trades": perf.get("total_trades", 0),
                    "Wins": perf.get("win_count", 0),
                    "Losses": perf.get("loss_count", 0),
                    "Total P&L": perf.get("total_realized_pnl", 0),
                    "Avg Win": perf.get("avg_win", 0),
                    "Avg Loss": perf.get("avg_loss", 0),
                    "P/L Ratio": perf.get("pl_ratio", 0),
                    "Max Consec Wins": perf.get("max_consecutive_wins", 0),
                    "Max Consec Losses": perf.get("max_consecutive_losses", 0),
                    "Avg Duration (Days)": perf.get("avg_trade_duration_days", 0),
                })
            if perf_rows:
                pd.DataFrame(perf_rows).to_excel(writer, sheet_name="Performance", index=False)

            # Trades
            all_trades = []
            for sym, result in results.items():
                for t in result.get("trades", []):
                    t_copy = dict(t)
                    t_copy["symbol"] = sym
                    all_trades.append(t_copy)
            if all_trades:
                pd.DataFrame(all_trades).to_excel(writer, sheet_name="Trades", index=False)

            # AI Analysis
            if ai_analysis:
                ai_rows = []
                ratings = ai_analysis.get("symbol_ratings", {})
                for sym, rating in ratings.items():
                    ai_rows.append({
                        "Symbol": sym,
                        "Overall Score": rating.get("overall_score", 0),
                        "Recommendation": rating.get("recommendation", ""),
                        "Profitability Score": rating.get("profitability_score", 0),
                        "Risk Score": rating.get("risk_score", 0),
                        "Consistency Score": rating.get("consistency_score", 0),
                        "Volatility": rating.get("volatility", ""),
                        "Total Return %": rating.get("total_return_pct", 0),
                        "Sharpe": rating.get("sharpe_ratio", 0),
                        "Max DD %": rating.get("max_drawdown_pct", 0),
                    })
                if ai_rows:
                    pd.DataFrame(ai_rows).to_excel(writer, sheet_name="AI Analysis", index=False)

            # Equity curves
            eq_rows = []
            for sym, result in results.items():
                for entry in result.get("equity_curve", []):
                    eq_rows.append({
                        "symbol": sym,
                        "timestamp": entry.get("timestamp", ""),
                        "equity": entry.get("equity", 0),
                        "cash": entry.get("cash", 0),
                    })
            if eq_rows:
                df_eq = pd.DataFrame(eq_rows)
                df_eq["timestamp"] = pd.to_datetime(df_eq["timestamp"], utc=True)
                pivot = df_eq.pivot(index="timestamp", columns="symbol", values="equity").reset_index()
                pivot.to_excel(writer, sheet_name="Equity Curves", index=False)

        logger.info(f"Exported Excel to {path}")
        return str(path)

    def export_pdf(self, results: Dict, ai_analysis: Optional[Dict] = None, filename: str = "report.pdf") -> str:
        """Export a professional PDF report."""
        path = self.output_dir / filename
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, Image
            )
            from reportlab.graphics.shapes import Drawing
        except ImportError:
            logger.error("reportlab not installed. pip install reportlab")
            return ""

        doc = SimpleDocTemplate(
            str(path), pagesize=letter,
            leftMargin=0.5 * inch, rightMargin=0.5 * inch,
            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        )
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph("Stratum — Backtest Report", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        story.append(Spacer(1, 20))

        # Performance Table
        perf_data = [["Symbol", "Return%", "Sharpe", "MaxDD%", "Win Rate%", "Trades", "P&L"]]
        for sym, result in results.items():
            if "performance" not in result:
                continue
            p = result["performance"]
            perf_data.append([
                sym,
                f"{p.get('total_return_pct', 0):+.2f}%",
                f"{p.get('sharpe_ratio', 0):.2f}",
                f"{p.get('max_drawdown_pct', 0):.2f}%",
                f"{p.get('win_rate', 0):.1f}%",
                str(p.get('total_trades', 0)),
                f"${p.get('total_realized_pnl', 0):,.2f}",
            ])

        t = Table(perf_data, colWidths=[0.8*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.8*inch, 0.6*inch, 1*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0891b2")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f9ff"), colors.white]),
        ]))
        story.append(Paragraph("Performance Summary", styles["Heading2"]))
        story.append(Spacer(1, 8))
        story.append(t)
        story.append(Spacer(1, 20))

        # AI Analysis
        if ai_analysis:
            story.append(Paragraph("AI Analysis", styles["Heading2"]))
            story.append(Spacer(1, 8))
            summary = ai_analysis.get("summary", "")
            story.append(Paragraph(summary, styles["Normal"]))
            story.append(Spacer(1, 12))

            ratings = ai_analysis.get("symbol_ratings", {})
            if ratings:
                ai_data = [["Symbol", "Score", "Recommendation", "Volatility"]]
                for sym, r in ratings.items():
                    rec = r.get("recommendation", "")
                    ai_data.append([
                        sym,
                        f"{r.get('overall_score', 0):.0f}/100",
                        rec,
                        r.get("volatility", ""),
                    ])
                t2 = Table(ai_data, colWidths=[0.8*inch, 0.7*inch, 1.5*inch, 0.8*inch])
                t2.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#059669")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]))
                story.append(t2)
                story.append(Spacer(1, 20))

        # Trade List (first 50)
        trade_count = sum(len(r.get("trades", [])) for r in results.values())
        if trade_count > 0:
            story.append(Paragraph("Recent Trades", styles["Heading2"]))
            story.append(Spacer(1, 8))
            trade_rows = [["Symbol", "Side", "Entry", "Exit", "P&L", "Reason"]]
            count = 0
            for sym, result in results.items():
                for t in result.get("trades", []):
                    if count >= 30:
                        break
                    trade_rows.append([
                        t.get("symbol", sym),
                        t.get("side", "").upper(),
                        f"${t.get('entry_price', 0):.2f}",
                        f"${t.get('exit_price', 0):.2f}",
                        f"${t.get('pnl', 0):+.2f}",
                        t.get("exit_reason", ""),
                    ])
                    count += 1
            t3 = Table(trade_rows, colWidths=[0.6*inch, 0.5*inch, 0.7*inch, 0.7*inch, 0.7*inch, 1*inch])
            t3.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d97706")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fff7ed"), colors.white]),
            ]))
            story.append(t3)

        doc.build(story)
        logger.info(f"Exported PDF to {path}")
        return str(path)

    def _sanitize(self, obj: Any) -> Any:
        """Sanitize objects for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj
