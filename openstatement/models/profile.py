import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths


@dataclass
class BankProfile:
    name: str
    headers: list[str]
    delimiter: str
    field_map: dict[str, str]
    debit_col: str
    credit_col: str
    use_split_amounts: bool
    date_format: str
    dayfirst: bool
    account_type: str
    account_id: str
    currency: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BankProfile":
        return cls(
            name=raw.get("name", ""),
            headers=raw.get("headers", []),
            delimiter=raw.get("delimiter", ","),
            field_map=raw.get("field_map", {}),
            debit_col=raw.get("debit_col", ""),
            credit_col=raw.get("credit_col", ""),
            use_split_amounts=bool(raw.get("use_split_amounts", False)),
            date_format=raw.get("date_format", ""),
            dayfirst=bool(raw.get("dayfirst", False)),
            account_type=raw.get("account_type", "CHECKING"),
            account_id=raw.get("account_id", ""),
            currency=raw.get("currency", "USD"),
        )


class ProfileStore:
    def __init__(self) -> None:
        app_data = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        root = Path(app_data) if app_data else Path.home() / ".openstatement"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "bank_profiles.json"

    def load(self) -> dict[str, BankProfile]:
        if not self.path.exists():
            return {}

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

        return {name: BankProfile.from_dict(item) for name, item in raw.items()}

    def save(self, profiles: dict[str, BankProfile]) -> None:
        serializable = {name: asdict(profile) for name, profile in profiles.items()}
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(serializable, handle, indent=2)


def normalize_header(value: str) -> str:
    return value.strip().casefold()


def to_account_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().casefold()).strip("_")
    return slug or "default_account"


def quote_py_string(value: str) -> str:
    return repr(value)
