"""Licensing System — Integrates with the Woven Model Licensing Server.

Supports 24-hour trial mode with feature gating for unlicensed users.
Activated licenses validate against the remote licensing server and cache
signed certificates locally for offline use.
"""
from __future__ import annotations

import json
import logging
import hashlib
import platform
import sys
import uuid
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta, timezone
import os

logger = logging.getLogger("Stratum.Licensing")

LICENSE_DIR = Path(__file__).resolve().parent.parent

# Add the client SDK to the Python path if available
SDK_PATHS = [
    # Development: relative to stratum/
    str(LICENSE_DIR / ".." / "licensing-server" / "client-sdk"),
    # Development: relative to End Product/
    str(LICENSE_DIR / ".." / "licensing-server" / "client-sdk"),
    # Production: installed as package
]
for sdk_path in SDK_PATHS:
    resolved = Path(sdk_path).resolve()
    if resolved.is_dir() and str(resolved) not in sys.path:
        sys.path.insert(0, str(resolved))

try:
    from woven_license import LicenseClient, LicenseConfig
    from woven_license.exceptions import (
        LicenseActivationError,
        LicenseValidationError,
        LicenseNetworkError,
        LicenseExpiredError,
        LicenseOfflineError,
    )
    HAS_SDK = True
except ImportError as e:
    HAS_SDK = False
    logger.warning(f"Woven License SDK not available: {e}. Using fallback licensing.")

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography not installed. Using fallback license storage.")

_APP_SECRET = b"Stratum2024WovenModelSecureKey!"

# Default licensing server URL (configurable via settings)
DEFAULT_LICENSING_SERVER_URL = "http://localhost:8000"

# Feature flags — which features are available in trial vs licensed mode
FEATURES = {
    "backtest": {"trial": True, "license": True, "trial_limit_symbols": 2},
    "ai_analysis": {"trial": False, "license": True},
    "optimization": {"trial": False, "license": True},
    "export_pdf": {"trial": False, "license": True},
    "export_excel": {"trial": False, "license": True},
    "export_csv": {"trial": False, "license": True},
    "export_json": {"trial": False, "license": True},
    "per_symbol_settings": {"trial": False, "license": True},
    "watchlist_save": {"trial": True, "license": True},
    "profiles_save": {"trial": False, "license": True},
    "profiles_load": {"trial": True, "license": True},
    "multi_symbol": {"trial": True, "license": True, "trial_limit": 2},
}


class LicenseManager:
    """Manages license activation, validation, trial tracking, and feature gating.

    Uses the Woven Model Licensing Server for online activation/validation
    and falls back to local encrypted storage for offline scenarios.
    """

    def __init__(
        self,
        license_file: Optional[str] = None,
        server_url: Optional[str] = None,
        product_code: str = "STRATUM",
        app_version: str = "1.2.0",
    ):
        self.license_file = Path(license_file or LICENSE_DIR / "license.lic")
        self._trial_mode = False
        self._trial_hours = 24
        self._license_data: Optional[Dict] = None
        self._activated = False
        self._machine_id = self._generate_machine_id()
        self._sdk_client = None
        self._server_url = server_url or DEFAULT_LICENSING_SERVER_URL

        # Initialize SDK client if available
        if HAS_SDK and self._server_url:
            try:
                sdk_config = LicenseConfig(
                    server_url=self._server_url,
                    product_code=product_code,
                    app_version=app_version,
                    cache_dir=str(LICENSE_DIR / "cache" / "license"),
                )
                self._sdk_client = LicenseClient(sdk_config)
                logger.debug(f"License SDK initialized for {self._server_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize License SDK: {e}")

    def _generate_machine_id(self) -> str:
        """Generate a unique machine identifier."""
        try:
            machine = platform.node()
            processor = platform.processor()
            system = platform.system()
            raw = f"{machine}-{processor}-{system}-{uuid.getnode()}"
            return hashlib.sha256(raw.encode()).hexdigest()[:32]
        except Exception:
            return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive an encryption key from the app secret + salt."""
        if not HAS_CRYPTO:
            return b""
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        return base64.urlsafe_b64encode(kdf.derive(_APP_SECRET))

    def _encrypt(self, data: Dict) -> str:
        """Encrypt license data to string."""
        if not HAS_CRYPTO:
            raw = json.dumps(data).encode()
            return base64.b64encode(raw).decode()
        salt = os.urandom(16)
        key = self._derive_key(salt)
        f = Fernet(key)
        encrypted = f.encrypt(json.dumps(data).encode())
        return base64.b64encode(salt + encrypted).decode()

    def _decrypt(self, data_str: str) -> Optional[Dict]:
        """Decrypt license data from string."""
        try:
            raw = base64.b64decode(data_str.encode())
            if not HAS_CRYPTO:
                return json.loads(raw)
            salt = raw[:16]
            encrypted = raw[16:]
            key = self._derive_key(salt)
            f = Fernet(key)
            decrypted = f.decrypt(encrypted)
            return json.loads(decrypted)
        except Exception as e:
            logger.debug(f"License decrypt failed: {e}")
            return None

    # Checksum validation characters — matches licensing server charset
    # Excludes ambiguous characters: 0, O, 1, I, L
    _LICENSE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    _CHAR_TO_VAL = {c: i for i, c in enumerate(_LICENSE_CHARS)}

    def _validate_license_key_format(self, key: str) -> bool:
        """Validate license key format and checksum (XXXXX-XXXXX-XXXXX-XXXXX).
        Checksum: sum of all 20 char values must be divisible by 36."""
        try:
            parts = key.strip().split("-")
            if len(parts) != 4:
                return False
            clean = "".join(parts).upper()
            if len(clean) != 20:
                return False
            for c in clean:
                if c not in self._CHAR_TO_VAL:
                    return False
            total = sum(self._CHAR_TO_VAL[c] for c in clean)
            return total % 36 == 0
        except Exception:
            return False

    def activate(self, license_key: str) -> Tuple[bool, str]:
        """Activate the application with a license key via the licensing server."""
        # First-pass format validation
        if not self._validate_license_key_format(license_key):
            return False, "Invalid license key. Expected XXXXX-XXXXX-XXXXX-XXXXX format with valid checksum."

        # Try server activation via SDK
        if self._sdk_client:
            try:
                result = self._sdk_client.activate(license_key)
                if result.success:
                    # Extract license data from server certificate
                    cert = result.data.get("certificate", {})
                    license_data = {
                        "license_key": license_key,
                        "machine_id": self._machine_id,
                        "activated_at": datetime.now(timezone.utc).isoformat(),
                        "expires_at": cert.get("expiration_date"),
                        "version": "1.0.0",
                        "product": "Stratum",
                        "features": cert.get("feature_flags", ["all"]),
                        "server_verified": True,
                    }
                    self._license_data = license_data
                    self._activated = True
                    self._trial_mode = False
                    # Remove trial file if exists
                    trial_file = LICENSE_DIR / ".trial"
                    if trial_file.exists():
                        trial_file.unlink()
                    self._save_to_file(license_data)
                    return True, "License activated successfully via server! All features unlocked."
            except LicenseActivationError as e:
                return False, str(e)
            except LicenseNetworkError:
                logger.warning("Server unreachable during activation. Falling back to local.")
            except Exception as e:
                logger.warning(f"Server activation failed: {e}. Falling back to local.")

        # Fallback: local activation (offline mode)
        if self.license_file.exists():
            existing = self._load_from_file()
            if existing and existing.get("machine_id") != self._machine_id:
                return False, "License already activated on another machine."

        now = datetime.now(timezone.utc)
        license_data = {
            "license_key": license_key,
            "machine_id": self._machine_id,
            "activated_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
            "version": "1.0.0",
            "product": "Stratum",
            "features": ["all"],
            "server_verified": False,
        }

        self._license_data = license_data
        self._activated = True
        self._trial_mode = False
        trial_file = LICENSE_DIR / ".trial"
        if trial_file.exists():
            trial_file.unlink()
        self._save_to_file(license_data)
        return True, "License activated locally! All features unlocked."

    def check_license(self) -> Tuple[bool, str]:
        """Check if the application is properly licensed (full or trial)."""
        # Check for existing license file
        if self.license_file.exists():
            data = self._load_from_file()
            if data is None:
                return False, "License file corrupted. Please re-activate."

            if data.get("machine_id") != self._machine_id:
                return False, "License tied to different machine. Please re-activate."

            expires_at = data.get("expires_at")
            if expires_at:
                try:
                    exp = datetime.fromisoformat(expires_at)
                    if exp < datetime.now(timezone.utc):
                        return False, "License has expired. Please renew."
                except ValueError:
                    pass

            self._license_data = data
            self._activated = True

            # Online re-validation via SDK (non-blocking: if server is down, use cache)
            if self._sdk_client and data.get("server_verified"):
                try:
                    validated = self._sdk_client.validate()
                    if not validated:
                        # Server says invalid — check cache
                        try:
                            if self._sdk_client.offline_validate():
                                logger.debug("License valid (offline certificate)")
                            else:
                                logger.warning("License validation failed on server and offline")
                        except LicenseOfflineError:
                            # Cache expired, but we still have local file — allow it
                            logger.debug("Offline cache expired, using local license file")
                except (LicenseNetworkError, Exception) as e:
                    logger.debug(f"Server validation unavailable: {e}. Using cached license.")

            key_preview = data.get("license_key", "Unknown")[:8]
            exp_preview = str(expires_at or "Perpetual")[:10]
            verified = "🔒" if data.get("server_verified") else "🔐"
            return True, f"{verified} Licensed | Key: {key_preview}... | Expires: {exp_preview}"

        # Check trial
        trial_file = LICENSE_DIR / ".trial"
        if trial_file.exists():
            try:
                trial_data = json.loads(trial_file.read_text())
                start = datetime.fromisoformat(trial_data["started"])
                elapsed = datetime.now(timezone.utc) - start
                remaining_hours = self._trial_hours - (elapsed.total_seconds() / 3600)
                if remaining_hours > 0:
                    self._trial_mode = True
                    hours_remaining = int(remaining_hours)
                    mins_remaining = int((remaining_hours - hours_remaining) * 60)
                    return True, f"Trial | {hours_remaining}h {mins_remaining}m remaining (limited features)"
                else:
                    return False, "Trial period expired. Please activate a license key."
            except Exception:
                pass

        # Start new trial
        trial_data = {"started": datetime.now(timezone.utc).isoformat()}
        trial_file.write_text(json.dumps(trial_data))
        self._trial_mode = True
        return True, f"Trial started | {self._trial_hours}h remaining (limited features)"

    def is_feature_allowed(self, feature_name: str) -> Tuple[bool, str]:
        """Check if a specific feature is available in the current license state.
        Returns (allowed: bool, reason: str)."""
        feature_config = FEATURES.get(feature_name)
        if feature_config is None:
            return True, ""

        if self._activated:
            # Check if feature is in server-provided feature flags
            if self._license_data and self._license_data.get("features"):
                features = self._license_data["features"]
                if "all" in features or feature_name in features:
                    return True, ""
            # Fall back to static config
            if feature_config.get("license", False):
                return True, ""
            return False, "Feature not included in current license."

        if self._trial_mode:
            if feature_config.get("trial", False):
                return True, ""
            return False, "Feature requires a paid license."

        return False, "No active license."

    def get_trial_limit(self, feature_name: str) -> Optional[int]:
        """Get the trial limit value for a feature (e.g., max symbols)."""
        feature_config = FEATURES.get(feature_name)
        if feature_config and self._trial_mode:
            return feature_config.get("trial_limit")
        return None

    def is_activated(self) -> bool:
        return self._activated

    def is_trial(self) -> bool:
        return self._trial_mode

    def get_license_info(self) -> Optional[Dict]:
        return self._license_data

    def get_remaining_trial_time(self) -> Optional[str]:
        """Get human-readable remaining trial time."""
        trial_file = LICENSE_DIR / ".trial"
        if not trial_file.exists():
            return None
        try:
            trial_data = json.loads(trial_file.read_text())
            start = datetime.fromisoformat(trial_data["started"])
            elapsed = datetime.now(timezone.utc) - start
            remaining_seconds = (self._trial_hours * 3600) - elapsed.total_seconds()
            if remaining_seconds <= 0:
                return "Expired"
            hours = int(remaining_seconds // 3600)
            mins = int((remaining_seconds % 3600) // 60)
            return f"{hours}h {mins}m"
        except Exception:
            return None

    def deactivate(self) -> None:
        """Remove license file (deactivate). Attempts server deactivation."""
        # Try server deactivation
        if self._sdk_client and self._license_data:
            try:
                key = self._license_data.get("license_key", "")
                if key:
                    self._sdk_client.deactivate(key)
            except Exception as e:
                logger.debug(f"Server deactivation failed: {e}")

        # Remove local files regardless
        if self.license_file.exists():
            self.license_file.unlink()
        self._activated = False
        self._license_data = None
        self._trial_mode = False
        logger.info("License deactivated — server notified")

    def _save_to_file(self, data: Dict) -> None:
        """Save encrypted license to file."""
        encrypted = self._encrypt(data)
        self.license_file.write_text(encrypted)

    def _load_from_file(self) -> Optional[Dict]:
        """Load and decrypt license from file."""
        try:
            encrypted = self.license_file.read_text().strip()
            return self._decrypt(encrypted)
        except Exception:
            return None
