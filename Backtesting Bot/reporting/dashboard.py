"""
Harper Dashboard — Generates comprehensive console and HTML reports
showing backtest results, pattern discoveries, equity curves, and rankings.
"""
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import numpy as np

from patterns.detector import Pattern

logger = logging.getLogger("Harper.Dashboard")

# ── Harper Brand System ──────────────────────────────
# ── Harper / Woven Model Color System ──
# Matched from https://heeroyuy1.github.io/Heeroyuy1.github.ai/
# Adapted for professional fintech dashboard
HARPER_COLORS = {
    "bg_primary": "#0c1929",       # Deep navy (Woven Model dark interpretation)
    "bg_card": "#142235",          # Card surface
    "bg_card_hover": "#1a2d45",   # Card hover state
    "border": "#1e3754",          # Subtle navy border
    "border_accent": "#0891b220", # Woven teal accent at 12% opacity
    "text_primary": "#e8edf2",    # Primary text
    "text_secondary": "#8ba4bc",  # Secondary/label text
    "text_muted": "#5c7b99",      # Muted/subtle text
    "accent_teal": "#0891b2",     # Woven Model primary teal (cyan-600)
    "accent_emerald": "#059669",  # Emerald-600 (success)
    "accent_blue": "#0284c7",     # Sky-600 (info)
    "accent_amber": "#d97706",    # Amber-600 (warning)
    "positive": "#059669",        # Positive/success
    "negative": "#dc2626",        # Red-600 (negative)
    "header_gradient_start": "#0b1a2e",
    "header_gradient_end": "#12253e",
}


class Dashboard:
    """
    Generates reports: console summary, JSON export, and HTML dashboard.
    Branded as Harper — Woven Model market intelligence platform.
    """

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def print_console_summary(self, results: Dict, patterns: List[Pattern]):
        """Print a comprehensive console summary of all Harper results."""
        print("\n" + "=" * 80)
        print("  HARPER — HISTORICAL BACKTEST & PATTERN DISCOVERY RESULTS")
        print("=" * 80)

        # Performance by symbol
        print("\n  BACKTEST PERFORMANCE BY SYMBOL")
        print("-" * 80)
        print(f"{'Symbol':<8} {'Return%':>10} {'Sharpe':>8} {'MaxDD%':>8} "
              f"{'WinRate%':>10} {'Trades':>8} {'P&L':>12}")
        print("-" * 80)

        symbol_results = {}
        for sym, result in results.items():
            if "performance" not in result:
                continue
            perf = result["performance"]
            symbol_results[sym] = perf
            print(
                f"{sym:<8} {perf['total_return_pct']:>+9.2f}% {perf['sharpe_ratio']:>8.2f} "
                f"{perf['max_drawdown_pct']:>7.2f}% {perf['win_rate']:>9.1f}% "
                f"{perf['total_trades']:>8} ${perf['total_realized_pnl']:>11.2f}"
            )

        # Aggregated totals
        if symbol_results:
            total_return = sum(p["total_return_pct"] for p in symbol_results.values())
            total_pnl = sum(p["total_realized_pnl"] for p in symbol_results.values())
            total_trades = sum(p["total_trades"] for p in symbol_results.values())
            total_wins = sum(p["win_count"] for p in symbol_results.values())
            avg_sharpe = np.mean([p["sharpe_ratio"] for p in symbol_results.values()])
            avg_dd = np.mean([p["max_drawdown_pct"] for p in symbol_results.values()])

            print("-" * 80)
            print(
                f"{'TOTAL':<8} {total_return:>+9.2f}% {avg_sharpe:>8.2f} "
                f"{avg_dd:>7.2f}% {total_wins/total_trades*100 if total_trades else 0:>9.1f}% "
                f"{total_trades:>8} ${total_pnl:>11.2f}"
            )

        # Best and worst
        if symbol_results:
            best_sym = max(symbol_results, key=lambda k: symbol_results[k]["total_return_pct"])
            worst_sym = min(symbol_results, key=lambda k: symbol_results[k]["total_return_pct"])
            print(f"\n  Best performer: {best_sym} (+{symbol_results[best_sym]['total_return_pct']:.2f}%)")
            print(f"  Worst performer: {worst_sym} ({symbol_results[worst_sym]['total_return_pct']:+.2f}%)")

        # Pattern discoveries
        print("\n  PATTERN DISCOVERIES")
        print("-" * 80)
        if patterns:
            print(f"{'Confidence':>10} {'Type':<18} {'Symbol':<8} {'Direction':<10} {'WinRate':>8} {'Description'}")
            print("-" * 80)
            for p in patterns[:20]:
                print(
                    f"{p.confidence_score:>9.1%} {p.pattern_type:<18} {p.symbol:<8} "
                    f"{p.direction:<10} {p.win_rate:>7.1%} {p.description[:60]}"
                )
            if len(patterns) > 20:
                print(f"  ... and {len(patterns) - 20} more patterns")
        else:
            print("  No statistically significant patterns found.")

        # Pattern type breakdown
        if patterns:
            type_counts = {}
            for p in patterns:
                type_counts[p.pattern_type] = type_counts.get(p.pattern_type, 0) + 1
            print("\n  Pattern types discovered:")
            for ptype, count in sorted(type_counts.items()):
                print(f"    {ptype}: {count}")

        print("\n" + "=" * 80)

    def generate_html_dashboard(
        self,
        results: Dict,
        patterns: List[Pattern],
        optimization_results: Optional[Dict] = None,
        output_filename: str = "dashboard.html",
    ) -> str:
        """Generate Harper-branded interactive HTML dashboard."""
        path = self.output_dir / output_filename

        symbols_data = []
        for sym, result in results.items():
            if "performance" not in result:
                continue
            perf = result["performance"]
            symbols_data.append({
                "symbol": sym,
                "return": perf["total_return_pct"],
                "sharpe": perf["sharpe_ratio"],
                "max_dd": perf["max_drawdown_pct"],
                "win_rate": perf["win_rate"],
                "trades": perf["total_trades"],
                "pnl": perf["total_realized_pnl"],
            })

        patterns_data = [
            {
                "confidence": p.confidence_score,
                "type": p.pattern_type,
                "symbol": p.symbol,
                "direction": p.direction,
                "win_rate": p.win_rate,
                "probability": p.probability_of_occurrence,
                "description": p.description,
                "p_value": p.p_value,
            }
            for p in patterns[:50]
        ]

        html = self._render_harper_html(symbols_data, patterns_data, optimization_results)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"Harper dashboard saved to {path}")
        return str(path)

    def _render_harper_html(
        self,
        symbols: List[Dict],
        patterns: List[Dict],
        optimization: Optional[Dict] = None,
    ) -> str:
        """Generate the full Harper-branded HTML dashboard."""

        symbols_json = json.dumps(symbols)
        patterns_json = json.dumps(patterns)
        c = HARPER_COLORS  # shorthand

        # Symbol table rows
        symbol_rows = ""
        for s in sorted(symbols, key=lambda x: x["return"], reverse=True):
            symbol_rows += f"""
            <tr>
                <td><strong>{s['symbol']}</strong></td>
                <td class="{'positive' if s['return']>0 else 'negative'}">{s['return']:+.2f}%</td>
                <td>{s['sharpe']:.2f}</td>
                <td>{s['max_dd']:.2f}%</td>
                <td>{s['win_rate']:.1f}%</td>
                <td>{s['trades']}</td>
                <td class="{'positive' if s['pnl']>0 else 'negative'}">${s['pnl']:,.2f}</td>
            </tr>"""

        # Pattern rows
        pattern_rows = ""
        for p in patterns[:30]:
            cf = p["confidence"]
            conf_color = c["positive"] if cf > 0.8 else (c["accent_amber"] if cf > 0.6 else c["negative"])
            pattern_rows += f"""
            <tr>
                <td style="color:{conf_color}; font-weight:bold">{p['confidence']:.1%}</td>
                <td>{p['type']}</td>
                <td>{p['symbol']}</td>
                <td>{p['direction']}</td>
                <td>{p['win_rate']:.1%}</td>
                <td>{p['probability']:.1%}</td>
                <td>{p.get('p_value', 'N/A')}</td>
                <td>{p['description'][:80]}</td>
            </tr>"""

        # Optimization section
        opt_html = ""
        if optimization:
            opt_html = '<div class="section-title">Strategy Optimization</div>'
            for sym, run in optimization.items():
                if run.best_result:
                    opt_html += f"""
                    <div class="card">
                        <div class="card-title">{sym} — Best Parameters</div>
                        <table>
                            <tr><th>Parameter</th><th>Value</th></tr>
                            {"".join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in run.best_result.params.items())}
                            <tr><td><strong>Score</strong></td><td>{run.best_result.score:.3f}</td></tr>
                            <tr><td><strong>Sharpe</strong></td><td>{run.best_result.sharpe_ratio:.2f}</td></tr>
                            <tr><td><strong>Return</strong></td><td>{run.best_result.total_return_pct:.2f}%</td></tr>
                            <tr><td><strong>Max DD</strong></td><td>{run.best_result.max_drawdown_pct:.2f}%</td></tr>
                            <tr><td><strong>Win Rate</strong></td><td>{run.best_result.win_rate:.1f}%</td></tr>
                        </table>
                    </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Harper — Intelligent Woven Model Platform for Market Backtesting, Pattern Discovery & Predictive Analytics">
    <title>Harper | Market Intelligence Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: {c["bg_primary"]};
            color: {c["text_primary"]};
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* ── Filter Bar ── */
        .filter-bar {{
            background: {c["bg_card"]};
            border: 1px solid {c["border"]};
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1.5rem;
            display: flex; flex-wrap: wrap; gap: 1rem; align-items: center;
        }}
        .filter-bar label {{
            font-size: 0.8rem; font-weight: 600; color: {c["text_secondary"]};
            text-transform: uppercase; letter-spacing: 0.5px;
        }}
        .filter-bar select, .filter-bar input {{
            background: {c["bg_primary"]}; color: {c["text_primary"]};
            border: 1px solid {c["border"]}; border-radius: 8px;
            padding: 0.5rem 0.75rem; font-size: 0.85rem;
            font-family: inherit; outline: none;
            transition: border-color 0.2s;
        }}
        .filter-bar select:focus, .filter-bar input:focus {{
            border-color: {c["accent_teal"]};
        }}
        .filter-bar .chip-group {{
            display: flex; flex-wrap: wrap; gap: 0.4rem;
        }}
        .chip {{
            padding: 0.35rem 0.75rem; border-radius: 20px;
            font-size: 0.78rem; font-weight: 600; cursor: pointer;
            border: 1px solid {c["border"]}; background: {c["bg_primary"]};
            color: {c["text_secondary"]}; transition: all 0.15s;
            user-select: none;
        }}
        .chip.active {{
            background: {c["accent_teal"]}20; border-color: {c["accent_teal"]};
            color: {c["accent_teal"]};
        }}
        .chip:hover {{ border-color: {c["accent_teal"]}60; }}
        .btn-refresh {{
            background: linear-gradient(135deg, {c["accent_teal"]}, {c["accent_emerald"]});
            color: #fff; font-weight: 700; border: none; border-radius: 8px;
            padding: 0.5rem 1.25rem; font-size: 0.85rem; cursor: pointer;
            font-family: inherit; transition: opacity 0.2s;
        }}
        .btn-refresh:hover {{ opacity: 0.9; }}

        /* ── Header ── */
        .header {{
            background: linear-gradient(135deg, {c["header_gradient_start"]}, {c["header_gradient_end"]});
            border-bottom: 2px solid {c["border"]};
            padding: 1.5rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        .header-brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .header-logo {{
            width: 40px; height: 40px;
            background: linear-gradient(135deg, {c["accent_teal"]}, {c["accent_emerald"]});
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem; font-weight: 800; color: #0a0f1c;
        }}
        .header-title {{
            font-size: 1.5rem; font-weight: 700;
            background: linear-gradient(135deg, {c["accent_teal"]}, {c["accent_blue"]});
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .header-subtitle {{
            font-size: 0.85rem; color: {c["text_muted"]}; letter-spacing: 0.5px;
        }}
        .header-badge {{
            background: {c["bg_card"]}; border: 1px solid {c["border"]};
            border-radius: 8px; padding: 0.4rem 1rem;
            font-size: 0.8rem; color: {c["accent_teal"]}; font-weight: 600;
        }}

        /* ── Layout ── */
        .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}

        .section-title {{
            font-size: 1.35rem; font-weight: 700; color: {c["text_primary"]};
            margin: 2.5rem 0 1rem; padding-bottom: 0.5rem;
            border-bottom: 2px solid {c["border"]};
            display: flex; align-items: center; gap: 0.5rem;
        }}
        .section-title::before {{
            content: ''; width: 4px; height: 24px;
            background: linear-gradient(180deg, {c["accent_teal"]}, {c["accent_emerald"]});
            border-radius: 2px;
        }}

        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem; }}

        .card {{
            background: {c["bg_card"]};
            border: 1px solid {c["border"]};
            border-radius: 12px;
            padding: 1.5rem;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            border-color: {c["accent_teal"]}40;
            box-shadow: 0 4px 24px {c["accent_teal"]}10;
        }}
        .card-title {{
            font-size: 0.95rem; font-weight: 600; color: {c["text_secondary"]};
            margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.8px;
        }}

        .chart-container {{ width: 100%; height: 280px; position: relative; }}

        /* ── Tables ── */
        .table-wrapper {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
        th {{
            background: #0f172a;
            padding: 0.85rem 1rem; text-align: left;
            border-bottom: 2px solid {c["accent_teal"]}40;
            color: {c["text_secondary"]}; font-weight: 600; font-size: 0.8rem;
            text-transform: uppercase; letter-spacing: 0.6px;
            white-space: nowrap;
        }}
        td {{ padding: 0.7rem 1rem; border-bottom: 1px solid {c["border"]}; color: {c["text_primary"]}; }}
        tr:hover td {{ background: {c["bg_card_hover"]}; }}
        .positive {{ color: {c["positive"]}; font-weight: 600; }}
        .negative {{ color: {c["negative"]}; font-weight: 600; }}

        /* ── KPI Cards ── */
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .kpi-card {{
            background: {c["bg_card"]}; border: 1px solid {c["border"]};
            border-radius: 12px; padding: 1.25rem; text-align: center;
        }}
        .kpi-value {{ font-size: 1.8rem; font-weight: 800; color: {c["accent_teal"]}; }}
        .kpi-label {{ font-size: 0.78rem; color: {c["text_muted"]}; margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.5px; }}

        /* ── Footer ── */
        .footer {{
            margin-top: 3rem; padding: 1.5rem 2rem;
            border-top: 1px solid {c["border"]};
            text-align: center; font-size: 0.8rem; color: {c["text_muted"]};
            display: flex; flex-direction: column; gap: 0.3rem;
        }}
        .footer strong {{ color: {c["accent_teal"]}; }}

        canvas {{ max-height: 280px; }}

        @media (max-width: 768px) {{
            .container {{ padding: 1rem; }}
            .header {{ padding: 1rem; flex-direction: column; align-items: flex-start; }}
            th, td {{ padding: 0.5rem 0.6rem; font-size: 0.8rem; }}
        }}
    </style>
</head>
<body>

    <!-- ── Header ── -->
    <header class="header">
        <div class="header-brand">
            <img src="harper-logo.png" alt="Woven Model" style="height:40px;width:40px;border-radius:10px;border:1px solid #1e3754;">
            <div>
                <div class="header-title">Harper</div>
                <div class="header-subtitle">Woven Model · Market Intelligence Platform</div>
            </div>
        </div>
        <div class="header-badge">Historical Backtest & Pattern Discovery</div>
    </header>

    <div class="container">

        <!-- ── KPI Summary ── -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-value">{symbols[0]['return']:+.1f}%</div>
                <div class="kpi-label">Best Return ({sorted(symbols, key=lambda x: x['return'], reverse=True)[0]['symbol'] if symbols else '—'})</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{sum(s['trades'] for s in symbols)}</div>
                <div class="kpi-label">Total Trades</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{sum(s['sharpe'] for s in symbols)/len(symbols) if symbols else 0:.1f}</div>
                <div class="kpi-label">Avg Sharpe Ratio</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{len(patterns)}</div>
                <div class="kpi-label">Patterns Discovered</div>
            </div>
        </div>

        <!-- ── Filter Bar ── -->
        <div class="filter-bar">
            <div style="display:flex;flex-direction:column;gap:0.5rem;flex:1;min-width:280px;">
                <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                    <label>Symbols:</label>
                    <div class="chip-group" id="symbol-chips"></div>
                    <button class="btn-refresh" onclick="selectAll()" style="font-size:0.75rem;padding:0.3rem 0.7rem;">All</button>
                    <button class="btn-refresh" onclick="deselectAll()" style="font-size:0.75rem;padding:0.3rem 0.7rem;background:#374151;">None</button>
                    <span id="symbol-count" style="font-size:0.75rem;color:{c['text_muted']};"></span>
                </div>
                <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                    <label>Date Range:</label>
                    <select id="date-preset" onchange="applyDatePreset()" style="min-width:110px;">
                        <option value="5y" selected>5 Years</option>
                        <option value="1m">1 Month</option>
                        <option value="3m">3 Months</option>
                        <option value="6m">6 Months</option>
                        <option value="1y">1 Year</option>
                        <option value="3y">3 Years</option>
                        <option value="max">Max</option>
                        <option value="">Custom</option>
                    </select>
                    <input type="date" id="date-from" placeholder="From" onchange="clearDatePreset();refreshAll()">
                    <span style="color:{c['text_muted']};">to</span>
                    <input type="date" id="date-to" placeholder="To" onchange="clearDatePreset();refreshAll()">
                </div>
                <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;margin-top:0.25rem;">
                    <label>Initial Capital:</label>
                    <input type="number" id="initial-capital" value="100000" min="1000" max="1000000000" step="10000" style="width:130px;padding:0.35rem 0.5rem;font-size:0.8rem;">
                    <label>Custom Symbols:</label>
                    <input type="text" id="custom-symbols" placeholder="e.g. META, AMZN, MSFT, AMD" style="flex:1;min-width:200px;max-width:400px;">
                    <button class="btn-refresh" onclick="runHarper()" id="btn-run">🚀 Run Harper</button>
                    <span id="run-status" style="font-size:0.75rem;color:{c['accent_amber']};"></span>
                </div>
            </div>
        </div>

        <!-- ══════════════════════════════════════════════════════════ -->
        <!-- ── STRATEGY SELECTOR ── -->
        <!-- ══════════════════════════════════════════════════════════ -->
        <div class="filter-bar" id="strategy-bar">
            <div style="display:flex;flex-direction:column;gap:0.75rem;flex:1;">
                <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                    <label>Strategy:</label>
                    <select id="strategy-select" onchange="onStrategyChange()" style="min-width:160px;">
                        <option value="rsi_sma">RSI + SMA</option>
                        <option value="sma_crossover">SMA Crossover</option>
                        <option value="macd">MACD</option>
                        <option value="bollinger">Bollinger Bands</option>
                    </select>
                    <label style="display:flex;align-items:center;gap:0.35rem;cursor:pointer;">
                        <input type="checkbox" id="allow-shorts" onchange="updateShortLabel();localStorage.setItem('harper_shorts',this.checked)">
                        <span id="short-label" style="font-size:0.7rem;">Shorting: OFF</span>
                    </label>
                </div>
                <div id="strategy-params" style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;"></div>
            </div>
        </div>

        <!-- ── Performance Table ── -->
        <div class="section-title">Performance by Symbol</div>
        <div class="card">
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th><th>Total Return</th><th>Sharpe</th>
                            <th>Max DD</th><th>Win Rate</th><th>Trades</th><th>Realized P&L</th>
                        </tr>
                    </thead>
                    <tbody>{symbol_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- ── Charts ── -->
        <div class="section-title">Performance Analytics</div>
        <div class="grid">
            <div class="card">
                <div class="card-title">Return by Symbol</div>
                <div class="chart-container"><canvas id="returnsChart"></canvas></div>
            </div>
            <div class="card">
                <div class="card-title">Sharpe Ratio</div>
                <div class="chart-container"><canvas id="sharpeChart"></canvas></div>
            </div>
            <div class="card">
                <div class="card-title">Win Rate %</div>
                <div class="chart-container"><canvas id="winrateChart"></canvas></div>
            </div>
            <div class="card">
                <div class="card-title">Max Drawdown %</div>
                <div class="chart-container"><canvas id="ddChart"></canvas></div>
            </div>
        </div>

        {opt_html}

        <!-- ── Patterns ── -->
        <div class="section-title">Discovered Patterns</div>
        <div class="card">
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Confidence</th><th>Type</th><th>Symbol</th><th>Direction</th>
                            <th>Win Rate</th><th>Probability</th><th>P-Value</th><th>Description</th>
                        </tr>
                    </thead>
                    <tbody>{pattern_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- ── Pattern Charts ── -->
        <div class="section-title">Pattern Intelligence</div>
        <div class="grid">
            <div class="card">
                <div class="card-title">Confidence vs Win Rate</div>
                <div class="chart-container"><canvas id="confidenceChart"></canvas></div>
            </div>
            <div class="card">
                <div class="card-title">Pattern Distribution</div>
                <div class="chart-container"><canvas id="typeChart"></canvas></div>
            </div>
        </div>

        <!-- ══════════════════════════════════════════════════════════ -->
        <!-- ── PERFORMANCE ANALYTICS EXPLAINED ── -->
        <!-- ══════════════════════════════════════════════════════════ -->
        <div class="section-title">Performance Metrics Explained</div>
        <div class="card" style="font-size:0.85rem;line-height:1.8;">
            <table>
                <thead><tr><th style="width:140px;">Metric</th><th>What It Means</th><th>How to Read It</th></tr></thead>
                <tbody>
                    <tr>
                        <td><strong>Total Return</strong></td>
                        <td>How much the simulated account grew from start to end, expressed as a percentage of the original capital.</td>
                        <td>Higher = better. A +500% return means $100K became $600K. Negative means the strategy lost money.</td>
                    </tr>
                    <tr>
                        <td><strong>Sharpe Ratio</strong></td>
                        <td>Return relative to risk. Measures how much return you got per unit of volatility (price swings).</td>
                        <td>Above 1.0 = decent. Above 2.0 = excellent. Below 0 = worse than holding cash. Higher Sharpe means smoother, more consistent returns.</td>
                    </tr>
                    <tr>
                        <td><strong>Max Drawdown (Max DD)</strong></td>
                        <td>The largest peak-to-trough drop the account experienced. A 20% max DD means at some point the account was down 20% from its all-time high.</td>
                        <td>Lower = safer. Under 10% is conservative. 20-30% is moderate. Above 50% means the strategy had severe losing periods.</td>
                    </tr>
                    <tr>
                        <td><strong>Win Rate</strong></td>
                        <td>Percentage of trades that were profitable (closed above entry for longs, below for shorts).</td>
                        <td>50%+ is typical for trend strategies. A high win rate (80%+) with low returns may mean winners are small and losers are cut quickly. A low win rate (30%) can still be profitable if winners are much larger than losers.</td>
                    </tr>
                    <tr>
                        <td><strong>Total Trades</strong></td>
                        <td>How many complete round-trip trades (entry + exit) were executed during the backtest.</td>
                        <td>More trades = more statistical confidence in the results. Under 30 trades may be too few to draw conclusions.</td>
                    </tr>
                    <tr>
                        <td><strong>Realized P&L</strong></td>
                        <td>The actual dollar profit/loss from all closed trades combined.</td>
                        <td>This is your bottom line. Positive = strategy made money. Tracks the change from initial capital to final equity.</td>
                    </tr>
                    <tr>
                        <td><strong>P/L Ratio</strong></td>
                        <td>Average winning trade size divided by average losing trade size.</td>
                        <td>Above 1.0 means winners are bigger than losers on average. Even with a 40% win rate, a 3:1 P/L ratio can be highly profitable.</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- ══════════════════════════════════════════════════════════ -->
        <!-- ── PATTERN TYPES GUIDE ── -->
        <!-- ══════════════════════════════════════════════════════════ -->
        <div class="section-title">Pattern Types Explained</div>
        <div class="card" style="font-size:0.85rem;line-height:1.8;">
            <table>
                <thead><tr><th style="width:150px;">Pattern Type</th><th>What Harper Detects</th><th>Plain-Language Translation</th></tr></thead>
                <tbody>
                    <tr>
                        <td><strong>seasonal</strong></td>
                        <td>Consistent price behavior during specific months across multiple years. Uses binomial tests to determine if positive/negative months occur more often than random chance.</td>
                        <td>"This stock tends to go up (or down) during [month] — it happened in X out of Y years. This is statistically significant (p < 0.05), meaning it's unlikely to be random noise."</td>
                    </tr>
                    <tr>
                        <td><strong>day_of_week</strong></td>
                        <td>Specific weekdays where returns are consistently different from zero. Uses t-tests to see if average daily returns on that day are statistically meaningful.</td>
                        <td>"On [day], this stock's average daily change is meaningfully different from flat — suggesting a recurring weekly rhythm in how it trades."</td>
                    </tr>
                    <tr>
                        <td><strong>volume_spike</strong></td>
                        <td>Days where trading volume was more than 2x the 20-day average, and what happened to the price over the next 1-5 days after those spikes.</td>
                        <td>"When this stock has unusually heavy trading volume, the price tends to [go up/down] the next day. Heavy volume often signals institutional interest or news-driven moves."</td>
                    </tr>
                    <tr>
                        <td><strong>technical_setup</strong></td>
                        <td>RSI extremes (oversold below 30, overbought above 70) and the 5-day forward return after those signals trigger. Uses binomial tests to see if the forward direction is non-random.</td>
                        <td>"When RSI drops below 30 (oversold), the stock historically rebounds over the next week X% of the time. When RSI rises above 70 (overbought), the stock historically pulls back or continues trending depending on direction found."</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- ══════════════════════════════════════════════════════════ -->
        <!-- ── HOW TO READ PATTERNS ── -->
        <!-- ══════════════════════════════════════════════════════════ -->
        <div class="section-title">How to Read Patterns (Ledger)</div>
        <div class="card" style="font-size:0.85rem;line-height:1.8;">
            <table>
                <thead><tr><th style="width:140px;">Column</th><th>What It Means</th><th>How to Interpret</th></tr></thead>
                <tbody>
                    <tr>
                        <td><strong>Confidence</strong></td>
                        <td>A score from 0-100% representing how statistically reliable the pattern is. Based on p-value from significance testing.</td>
                        <td><span style="color:{c['positive']}">>80% = High confidence</span> (very unlikely to be random). <span style="color:{c['accent_amber']}">60-80% = Moderate</span>. <span style="color:{c['negative']}"><60% = Low confidence</span> — use cautiously.</td>
                    </tr>
                    <tr>
                        <td><strong>Type</strong></td>
                        <td>The category of pattern Harper discovered. See Pattern Types Guide above for detailed explanations.</td>
                        <td>Each type uses different detection methods. Seasonal = calendar-based. Technical = indicator-based. Volume = activity-based.</td>
                    </tr>
                    <tr>
                        <td><strong>Symbol</strong></td>
                        <td>The stock ticker where this pattern was detected.</td>
                        <td>Patterns are symbol-specific. A seasonal pattern in AAPL does not apply to TSLA.</td>
                    </tr>
                    <tr>
                        <td><strong>Direction</strong></td>
                        <td>Whether the pattern historically led to bullish (price-up) or bearish (price-down) outcomes.</td>
                        <td>Bullish patterns suggest buying opportunities. Bearish patterns suggest caution or short-selling setups.</td>
                    </tr>
                    <tr>
                        <td><strong>Win Rate</strong></td>
                        <td>How often the pattern's predicted direction was correct historically.</td>
                        <td>60%+ = consistently correct. 50-60% = slight edge. Under 50% = the opposite direction happened more often.</td>
                    </tr>
                    <tr>
                        <td><strong>Probability</strong></td>
                        <td>The historical frequency of the pattern occurring. A 70% probability means the pattern appeared in 7 out of 10 possible opportunities.</td>
                        <td>Higher probability = more frequent event. A rare event (low probability) still matters if it's highly profitable when it does occur.</td>
                    </tr>
                    <tr>
                        <td><strong>P-Value</strong></td>
                        <td>Statistical measure of whether the pattern could be random noise. Lower = more significant.</td>
                        <td>p < 0.05 = statistically significant (95%+ confidence it's not random). p < 0.01 = highly significant. p > 0.05 = may be random — treat with caution.</td>
                    </tr>
                    <tr>
                        <td><strong>Description</strong></td>
                        <td>Human-readable summary of what the pattern is, including historical counts and average outcomes.</td>
                        <td>Read this first to understand the pattern at a glance. Example: "META volume spikes: next day avg -0.97% (bearish), 9/15 follow direction" means 15 spike days occurred, 9 went down, average drop was 0.97%.</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- ══════════════════════════════════════════════════════════ -->
        <!-- ── IMPORTANT CONTEXT ── -->
        <!-- ══════════════════════════════════════════════════════════ -->
        <div class="section-title">Important Context</div>
        <div class="card" style="font-size:0.85rem;line-height:1.7;color:{c['text_secondary']};">
            <p><strong>Correlation is not causation.</strong> Every pattern Harper finds is a statistical relationship observed in historical data. These patterns may or may not repeat in the future.</p>
            <p style="margin-top:0.5rem;"><strong>Backtest results are simulated.</strong> The performance numbers shown are from paper trading with virtual money. They assume perfect fills at market prices with small slippage. Real trading involves spreads, commissions, and liquidity constraints that can reduce returns.</p>
            <p style="margin-top:0.5rem;"><strong>Sample size matters.</strong> Patterns with fewer than 10 occurrences should be treated as exploratory, not actionable. The more data points, the more reliable the statistical inference.</p>
            <p style="margin-top:0.5rem;"><strong>Market regime changes.</strong> Relationships that held from 2020-2025 may break down if market structure changes (e.g., interest rate shifts, regulatory changes, new market participants). Harper provides historical context — not guarantees.</p>
        </div>

    </div>

    <!-- ── Footer ── -->
    <footer class="footer">
        <div><strong>Harper</strong> · Woven Model Market Intelligence Platform</div>
        <div>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        <div>⚠️ Past performance does not guarantee future results. All patterns are statistical correlations, not predictions.</div>
    </footer>

    <script>
        const allSymbols = {symbols_json};
        const allPatterns = {patterns_json};
        let activeSymbols = new Set(allSymbols.map(s => s.symbol));
        let charts = {{}};

        // ── Populate symbol chips ──
        const chipGroup = document.getElementById('symbol-chips');
        const uniqueSymbols = [...new Set(allSymbols.map(s => s.symbol))];
        uniqueSymbols.forEach(sym => {{
            const chip = document.createElement('span');
            chip.className = 'chip active';
            chip.textContent = sym;
            chip.onclick = () => {{
                if (activeSymbols.has(sym)) {{
                    activeSymbols.delete(sym);
                    chip.classList.remove('active');
                }} else {{
                    activeSymbols.add(sym);
                    chip.classList.add('active');
                }}
                refreshAll();
            }};
            chipGroup.appendChild(chip);
        }});

        function getFiltered() {{
            return allSymbols.filter(s => activeSymbols.has(s.symbol));
        }}
        function getFilteredPatterns() {{
            return allPatterns.filter(p => activeSymbols.has(p.symbol));
        }}

        function updateSymbolCount() {{
            const sel = activeSymbols.size;
            const total = uniqueSymbols.length;
            document.getElementById('symbol-count').textContent = sel + ' of ' + total + ' selected';
        }}
        function refreshAll() {{
            updateSymbolCount();
            const filtered = getFiltered();
            const fp = getFilteredPatterns();
            updateTable(filtered);
            updateKPIs(filtered, fp);
            updateCharts(filtered, fp);
        }}

        function updateTable(filtered) {{
            const tbody = document.querySelector('.card .table-wrapper tbody');
            const sorted = [...filtered].sort((a,b) => b.return - a.return);
            tbody.innerHTML = sorted.map(s =>
                `<tr>
                    <td><strong>${{s.symbol}}</strong></td>
                    <td class="${{s.return>0?'positive':'negative'}}">${{s.return.toFixed(2)}}%</td>
                    <td>${{s.sharpe.toFixed(2)}}</td>
                    <td>${{s.max_dd.toFixed(2)}}%</td>
                    <td>${{s.win_rate.toFixed(1)}}%</td>
                    <td>${{s.trades}}</td>
                    <td class="${{s.pnl>0?'positive':'negative'}}">$${{s.pnl.toLocaleString('en-US',{{minimumFractionDigits:2}})}}</td>
                </tr>`
            ).join('');
        }}

        function updateKPIs(filtered, fp) {{
            if (filtered.length === 0) return;
            const sorted = [...filtered].sort((a,b) => b.return - a.return);
            const kpis = document.querySelectorAll('.kpi-value');
            kpis[0].textContent = `${{sorted[0].return >= 0 ? '+' : ''}}${{sorted[0].return.toFixed(1)}}%`;
            kpis[0].nextElementSibling.textContent = `Best Return (${{sorted[0].symbol}})`;
            kpis[1].textContent = filtered.reduce((a,s) => a + s.trades, 0);
            kpis[2].textContent = (filtered.reduce((a,s) => a + s.sharpe, 0) / filtered.length).toFixed(1);
            kpis[3].textContent = fp.length;
        }}

        function selectAll() {{
            document.querySelectorAll('#symbol-chips .chip').forEach(c => {{
                c.classList.add('active');
                activeSymbols.add(c.textContent);
            }});
            refreshAll();
        }}
        function deselectAll() {{
            document.querySelectorAll('#symbol-chips .chip').forEach(c => {{
                c.classList.remove('active');
                activeSymbols.delete(c.textContent);
            }});
            refreshAll();
        }}

        function destroyCharts() {{
            Object.values(charts).forEach(c => c.destroy());
            charts = {{}};
        }}

        const cd = {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                y: {{ ticks: {{ color: '#8ba4bc' }}, grid: {{ color: '#1e375430' }} }},
                x: {{ ticks: {{ color: '#8ba4bc' }}, grid: {{ display: false }} }}
            }}
        }};

        function updateCharts(filtered, fp) {{
            destroyCharts();
            if (filtered.length === 0) return;
            const labels = filtered.map(s => s.symbol);
            charts.returns = new Chart(document.getElementById('returnsChart'), {{
                type: 'bar', data: {{ labels, datasets: [{{
                    data: filtered.map(s => s.return),
                    backgroundColor: filtered.map(s => s.return>=0?'#05966955':'#dc262655'),
                    borderColor: filtered.map(s => s.return>=0?'#059669':'#dc2626'),
                    borderWidth: 2, borderRadius: 6
                }}] }}, options: cd
            }});
            charts.sharpe = new Chart(document.getElementById('sharpeChart'), {{
                type: 'bar', data: {{ labels, datasets: [{{
                    data: filtered.map(s => s.sharpe),
                    backgroundColor: '#0891b255', borderColor: '#0891b2',
                    borderWidth: 2, borderRadius: 6
                }}] }}, options: cd
            }});
            charts.winrate = new Chart(document.getElementById('winrateChart'), {{
                type: 'bar', data: {{ labels, datasets: [{{
                    data: filtered.map(s => s.win_rate),
                    backgroundColor: '#0284c755', borderColor: '#0284c7',
                    borderWidth: 2, borderRadius: 6
                }}] }}, options: {{...cd, scales:{{...cd.scales, y:{{...cd.scales.y, min:0, max:100}}}}}}
            }});
            charts.dd = new Chart(document.getElementById('ddChart'), {{
                type: 'bar', data: {{ labels, datasets: [{{
                    data: filtered.map(s => s.max_dd),
                    backgroundColor: '#dc262655', borderColor: '#dc2626',
                    borderWidth: 2, borderRadius: 6
                }}] }}, options: {{...cd, scales:{{...cd.scales, y:{{...cd.scales.y, reverse:true}}}}}}
            }});
            if (fp.length > 0) {{
                charts.confidence = new Chart(document.getElementById('confidenceChart'), {{
                    type: 'scatter', data: {{ datasets: [{{
                        data: fp.map(p => ({{x:p.confidence, y:p.win_rate}})),
                        backgroundColor: fp.map(p => p.direction==='bullish'?'#059669':'#dc2626')
                    }}] }}, options: {{
                        responsive:true, maintainAspectRatio:false,
                        scales: {{
                            x: {{ title: {{display:true, text:'Confidence', color:'#8ba4bc'}}, ticks: {{color:'#8ba4bc'}} }},
                            y: {{ title: {{display:true, text:'Win Rate', color:'#8ba4bc'}}, ticks: {{color:'#8ba4bc'}} }}
                        }}
                    }}
                }});
                const tc = {{}}; fp.forEach(p => {{ tc[p.type]=(tc[p.type]||0)+1; }});
                charts.typeChart = new Chart(document.getElementById('typeChart'), {{
                    type: 'doughnut', data: {{ labels: Object.keys(tc), datasets: [{{
                        data: Object.values(tc),
                        backgroundColor: ['#0891b2','#0284c7','#d97706','#a78bfa','#dc2626'],
                        borderColor: '#142235', borderWidth: 3
                    }}] }}, options: {{
                        responsive:true, maintainAspectRatio:false,
                        plugins: {{ legend: {{ labels: {{ color:'#8ba4bc', padding:16 }} }} }}
                    }}
                }});
            }}
        }}

        // ── Strategy Selector ──
        const strategyParams = {{
            rsi_sma: [
                {{id:'rsi_period', label:'RSI Period', type:'number', value:'14', min:'5', max:'50'}},
                {{id:'rsi_buy', label:'Buy Below', type:'number', value:'30', min:'10', max:'45'}},
                {{id:'rsi_sell', label:'Sell Above', type:'number', value:'70', min:'55', max:'90'}},
                {{id:'sma_period', label:'SMA Period', type:'number', value:'20', min:'5', max:'200'}},
                {{id:'stop_loss', label:'Stop Loss %', type:'number', value:'2', min:'0.5', max:'10', step:'0.5'}},
                {{id:'take_profit', label:'Take Profit %', type:'number', value:'5', min:'1', max:'20', step:'0.5'}},
            ],
            sma_crossover: [
                {{id:'sma_fast', label:'Fast SMA', type:'number', value:'10', min:'3', max:'50'}},
                {{id:'sma_slow', label:'Slow SMA', type:'number', value:'50', min:'20', max:'200'}},
                {{id:'stop_loss', label:'Stop Loss %', type:'number', value:'2', min:'0.5', max:'10', step:'0.5'}},
                {{id:'take_profit', label:'Take Profit %', type:'number', value:'5', min:'1', max:'20', step:'0.5'}},
            ],
            macd: [
                {{id:'macd_fast', label:'Fast EMA', type:'number', value:'12', min:'5', max:'50'}},
                {{id:'macd_slow', label:'Slow EMA', type:'number', value:'26', min:'10', max:'100'}},
                {{id:'macd_signal', label:'Signal EMA', type:'number', value:'9', min:'3', max:'30'}},
                {{id:'stop_loss', label:'Stop Loss %', type:'number', value:'2', min:'0.5', max:'10', step:'0.5'}},
                {{id:'take_profit', label:'Take Profit %', type:'number', value:'5', min:'1', max:'20', step:'0.5'}},
            ],
            bollinger: [
                {{id:'bb_period', label:'BB Period', type:'number', value:'20', min:'10', max:'100'}},
                {{id:'bb_std', label:'Std Deviations', type:'number', value:'2', min:'1', max:'4', step:'0.5'}},
                {{id:'stop_loss', label:'Stop Loss %', type:'number', value:'2', min:'0.5', max:'10', step:'0.5'}},
                {{id:'take_profit', label:'Take Profit %', type:'number', value:'5', min:'1', max:'20', step:'0.5'}},
            ],
        }};

        function onStrategyChange() {{
            const sel = document.getElementById('strategy-select').value;
            const container = document.getElementById('strategy-params');
            container.innerHTML = '';
            const params = strategyParams[sel] || [];
            params.forEach(p => {{
                const span = document.createElement('span');
                span.style.cssText = 'display:flex;align-items:center;gap:0.3rem;';
                span.innerHTML = `<label style="font-size:0.7rem;">${{p.label}}:</label>
                    <input type="${{p.type}}" id="param-${{p.id}}" value="${{p.value}}"
                    min="${{p.min||''}}" max="${{p.max||''}}" step="${{p.step||'1'}}"
                    style="width:70px;padding:0.3rem 0.5rem;font-size:0.75rem;">`;
                container.appendChild(span);
            }});
        }}
        onStrategyChange(); // init on load

        function getStrategyConfig() {{
            const strategy = document.getElementById('strategy-select').value;
            const params = {{}};
            const inputs = document.querySelectorAll('#strategy-params input');
            inputs.forEach(inp => {{
                const key = inp.id.replace('param-', '');
                params[key] = inp.type === 'number' ? parseFloat(inp.value) : inp.value;
            }});
            return {{strategy, params}};
        }}

        // ── Date Preset Helper ──
        function applyDatePreset() {{
            const preset = document.getElementById('date-preset').value;
            if (!preset) return;
            localStorage.setItem('harper_date_preset', preset);
            if (!preset) return;
            const now = new Date();
            const to = now.toISOString().split('T')[0];
            let from;
            switch(preset) {{
                case '1m': from = new Date(now.getFullYear(), now.getMonth()-4, now.getDate()); break;
                case '3m': from = new Date(now.getFullYear(), now.getMonth()-6, now.getDate()); break;
                case '6m': from = new Date(now.getFullYear(), now.getMonth()-6, now.getDate()); break;
                case '1y': from = new Date(now.getFullYear()-1, now.getMonth(), now.getDate()); break;
                case '3y': from = new Date(now.getFullYear()-3, now.getMonth(), now.getDate()); break;
                case '5y': from = new Date(now.getFullYear()-5, now.getMonth(), now.getDate()); break;
                case 'max': from = new Date(2000, 0, 1); break;
                default: return;
            }}
            document.getElementById('date-from').value = from.toISOString().split('T')[0];
            document.getElementById('date-to').value = to;
            refreshAll();
        }}
        function clearDatePreset() {{
            document.getElementById('date-preset').value = '';
        }}

        // ── Custom symbols / Re-run ──
        async function runHarper() {{
            const input = document.getElementById('custom-symbols');
            const customSymbols = input.value.trim();
            // Use custom symbols if provided, otherwise fall back to currently selected chip symbols
            let symbols = customSymbols;
            if (!symbols) {{
                // Use the symbols from the active chips
                if (activeSymbols.size === 0) {{
                    document.getElementById('run-status').textContent = 'Select symbols or enter custom ones';
                    return;
                }}
                symbols = [...activeSymbols].join(',');
            }}
            const btn = document.getElementById('btn-run');
            const status = document.getElementById('run-status');
            btn.disabled = true;
            btn.textContent = '⏳ Running...';
            status.textContent = 'Starting Harper...';
            status.style.color = '{c["accent_amber"]}';
            try {{
                const capital = parseFloat(document.getElementById('initial-capital').value) || 100000;
                const strategyConfig = getStrategyConfig();
                const allowShorts = document.getElementById('allow-shorts').checked;
                const dateFrom = document.getElementById('date-from').value || '';
                const dateTo = document.getElementById('date-to').value || '';
                const resp = await fetch('/api/run', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        symbols: symbols,
                        strategy: strategyConfig,
                        initial_capital: capital,
                        allow_shorts: allowShorts,
                        start_date: dateFrom || null,
                        end_date: dateTo || null
                    }})
                }});
                const data = await resp.json();
                if (resp.ok) {{
                    status.textContent = 'Running for ' + data.symbols.join(', ') + '... (may take 1-2 min)';
                    pollStatus();
                }} else {{
                    status.textContent = 'Error: ' + (data.error || 'unknown');
                    status.style.color = '{c["negative"]}';
                    btn.disabled = false;
                    btn.textContent = '🚀 Run Harper';
                }}
            }} catch(err) {{
                status.textContent = 'Is Harper server running? (python server.py)';
                status.style.color = '{c["negative"]}';
                btn.disabled = false;
                btn.textContent = '🚀 Run Harper';
            }}
        }}

        function pollStatus() {{
            const interval = setInterval(async () => {{
                try {{
                    const resp = await fetch('/api/status');
                    const data = await resp.json();
                    const status = document.getElementById('run-status');
                    const btn = document.getElementById('btn-run');
                    status.textContent = data.progress || '';
                    if (!data.running) {{
                        clearInterval(interval);
                        btn.disabled = false;
                        btn.textContent = '🚀 Run Harper';
                        if (data.error) {{
                            status.textContent = 'Error: ' + data.error;
                            status.style.color = '{c["negative"]}';
                        }} else {{
                            status.textContent = 'Done! Reloading...';
                            status.style.color = '{c["positive"]}';
                            setTimeout(() => location.reload(), 1000);
                        }}
                    }}
                }} catch(e) {{ clearInterval(interval); }}
            }}, 2000);
        }}

        // ── Shorting toggle persistence ──
        function updateShortLabel() {{
            const cb = document.getElementById('allow-shorts');
            const label = document.getElementById('short-label');
            label.textContent = cb.checked ? 'Shorting: ON' : 'Shorting: OFF';
        }}
        // Restore shorting state from localStorage
        (function() {{
            const saved = localStorage.getItem('harper_shorts');
            if (saved !== null) {{
                document.getElementById('allow-shorts').checked = saved === 'true';
            }}
            updateShortLabel();
        }})();

        // Initial render
        updateCharts(getFiltered(), getFilteredPatterns());
        updateSymbolCount();
    </script>
</body>
</html>"""

    def export_json(self, results: Dict, patterns: List[Pattern], filename: str = "results.json"):
        """Export all Harper results as JSON."""
        path = self.output_dir / filename
        output = {
            "product": "Harper",
            "platform": "Woven Model Market Intelligence",
            "generated_at": datetime.now().isoformat(),
            "performance": {},
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "type": p.pattern_type,
                    "symbol": p.symbol,
                    "description": p.description,
                    "confidence": p.confidence_score,
                    "win_rate": p.win_rate,
                    "probability": p.probability_of_occurrence,
                    "direction": p.direction,
                    "p_value": p.p_value,
                    "metadata": p.metadata,
                }
                for p in patterns
            ],
        }
        for sym, result in results.items():
            if "performance" in result:
                output["performance"][sym] = {
                    **result["performance"],
                    "start_date": result.get("start_date"),
                    "end_date": result.get("end_date"),
                    "total_bars": result.get("total_bars"),
                }

        with open(path, "w") as f:
            json.dump(output, f, indent=2, default=str)
        logger.info(f"Harper JSON exported to {path}")
        return str(path)
