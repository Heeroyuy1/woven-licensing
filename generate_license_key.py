"""Stratum License Key Generator.
Run: python generate_license_key.py
Outputs valid license keys for the Stratum application in XXXXX-XXXXX-XXXXX-XXXXX format.

Uses a modulo-36 checksum: sum of all character values must be divisible by 36.
Character set excludes ambiguous characters (0, O, 1, I, L) — matches the licensing server."""
import random

# Matches licensing server charset: excludes ambiguous 0, O, 1, I, L
CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 32 chars (2^5), 36^20 key space
CHAR_TO_VAL = {c: i for i, c in enumerate(CHARS)}
VAL_TO_CHAR = {i: c for i, c in enumerate(CHARS)}


def generate_key() -> str:
    """Generate a valid license key using modulo-36 checksum."""
    # Generate first 19 random characters
    raw = ''.join(random.choices(CHARS, k=19))
    
    # Calculate checksum: sum of all char values must be a multiple of 36
    total = sum(CHAR_TO_VAL[c] for c in raw)
    checksum_val = (36 - (total % 36)) % 36
    checksum_char = VAL_TO_CHAR[checksum_val]
    
    full = raw + checksum_char
    key = '-'.join([full[i:i+5] for i in range(0, 20, 5)])
    return key


def validate_key(key: str) -> bool:
    """Validate a license key by checking its checksum."""
    try:
        clean = key.replace('-', '').upper()
        if len(clean) != 20:
            return False
        for c in clean:
            if c not in CHAR_TO_VAL:
                return False
        total = sum(CHAR_TO_VAL[c] for c in clean)
        return total % 36 == 0
    except Exception:
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Stratum License Key Generator")
    print("=" * 60)
    print()
    for i in range(5):
        k = generate_key()
        v = "✅" if validate_key(k) else "❌"
        print(f"  {i+1}. {k}  {v}")
    print()
    print("  Enter any key above in the License tab to activate.")
    print()
