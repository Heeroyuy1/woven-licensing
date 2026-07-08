"""Configuration Manager — Loads, saves, and manages strategy profiles."""
import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger("Stratum.Config")

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "profiles"

DEFAULT_SYMBOLS = ["AAPL", "TSLA", "NVDA", "GOOGL", "AMD"]

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": "Stratum",
    "version": "1.0.0",
    "symbols": DEFAULT_SYMBOLS,
    "start_date": "2020-01-01",
    "end_date": "2025-12-31",
    "interval": "1d",
    "initial_capital": 100000.0,
    "allow_shorts": True,
    "commission_per_share": 0.0,
    "slippage_pct": 0.0005,
    "strategy": {
        "name": "rsi_sma",
        "params": {
            "sma_period": 20,
            "rsi_period": 14,
            "rsi_buy_threshold": 30,
            "rsi_sell_threshold": 70,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.05,
            "max_loss_pct": 0.05,
            "max_holding_bars": 5,
            "max_exposure_pct": 0.1,
            "risk_pct": 0.01,
        },
    },
    "per_symbol_settings": {},
    "optimization": {
        "enabled": False,
        "scoring_metric": "composite",
        "param_grid": {
            "rsi_buy_threshold": [25, 28, 30, 33, 35],
            "rsi_sell_threshold": [65, 70, 72, 75, 78],
            "stop_loss_pct": [0.01, 0.015, 0.02, 0.025, 0.03],
            "take_profit_pct": [0.03, 0.04, 0.05, 0.06, 0.08],
        },
    },
    "ui": {
        "theme": "dark",
        "window_width": 1400,
        "window_height": 900,
        "maximized": True,
    },
}


@dataclass
class StrategyParams:
    sma_period: int = 20
    rsi_period: int = 14
    rsi_buy_threshold: float = 30.0
    rsi_sell_threshold: float = 70.0
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    max_loss_pct: float = 0.05
    max_holding_bars: int = 5
    max_exposure_pct: float = 0.1
    risk_pct: float = 0.01

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PerSymbolSettings:
    symbol: str
    rsi_period: int = 14
    rsi_buy_threshold: float = 30.0
    rsi_sell_threshold: float = 70.0
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    max_loss_pct: float = 0.05

    def to_dict(self) -> Dict:
        return asdict(self)


class ConfigManager:
    """Manages application configuration and strategy profiles."""

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or DEFAULT_CONFIG_PATH)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Any] = deepcopy(DEFAULT_CONFIG)
        self._current_profile: str = "default"
        self._loaded = False

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    def load(self, profile: str = "default") -> Dict[str, Any]:
        """Load configuration from a profile file."""
        path = self.config_dir / f"{profile}.json"
        if path.exists():
            try:
                with open(path) as f:
                    loaded = json.load(f)
                # Deep merge with defaults
                self._deep_merge(self._config, loaded)
                self._current_profile = profile
                self._loaded = True
                logger.info(f"Loaded profile '{profile}' from {path}")
            except Exception as e:
                logger.error(f"Failed to load profile '{profile}': {e}")
        else:
            logger.info(f"Profile '{profile}' not found, using defaults")
            self.save(profile)
        return self._config

    def save(self, profile: Optional[str] = None) -> None:
        """Save current configuration to a profile file."""
        profile = profile or self._current_profile
        path = self.config_dir / f"{profile}.json"
        try:
            with open(path, "w") as f:
                json.dump(self._config, f, indent=2, default=str)
            self._current_profile = profile
            logger.info(f"Saved profile '{profile}' to {path}")
        except Exception as e:
            logger.error(f"Failed to save profile '{profile}': {e}")

    def list_profiles(self) -> List[str]:
        """List all available profiles."""
        profiles = []
        for f in self.config_dir.glob("*.json"):
            profiles.append(f.stem)
        return sorted(profiles)

    def delete_profile(self, profile: str) -> bool:
        """Delete a profile file."""
        if profile == "default":
            return False
        path = self.config_dir / f"{profile}.json"
        if path.exists():
            path.unlink()
            logger.info(f"Deleted profile '{profile}'")
            return True
        return False

    def get_strategy_params(self, symbol: Optional[str] = None) -> StrategyParams:
        """Get strategy params, with per-symbol overrides if symbol provided."""
        params = StrategyParams(**self._config["strategy"]["params"])
        if symbol and symbol in self._config.get("per_symbol_settings", {}):
            overrides = self._config["per_symbol_settings"][symbol]
            for key, val in overrides.items():
                if hasattr(params, key):
                    setattr(params, key, val)
        return params

    def set_strategy_params(self, params: StrategyParams) -> None:
        """Update strategy params in config."""
        self._config["strategy"]["params"] = params.to_dict()

    def set_per_symbol_setting(self, symbol: str, key: str, value: Any) -> None:
        """Set a per-symbol config override."""
        if "per_symbol_settings" not in self._config:
            self._config["per_symbol_settings"] = {}
        if symbol not in self._config["per_symbol_settings"]:
            self._config["per_symbol_settings"][symbol] = {}
        self._config["per_symbol_settings"][symbol][key] = value

    def remove_per_symbol_settings(self, symbol: str) -> None:
        """Remove all per-symbol overrides for a symbol."""
        if symbol in self._config.get("per_symbol_settings", {}):
            del self._config["per_symbol_settings"][symbol]

    def reset_to_defaults(self) -> None:
        """Reset config to factory defaults."""
        self._config = deepcopy(DEFAULT_CONFIG)
        self._current_profile = "default"

    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """Recursively merge override dict into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
