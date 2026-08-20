import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

DEFAULT_FILENAME_PATTERN = "{account_name}_{account_id}_{statement_date}_{ending_balance}.csv"


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
    auto_parse_filename_metadata: bool
    filename_pattern: str
    has_header: bool
    leading_rows_to_skip: int = 0
    trailing_rows_to_skip: int = 0

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
            auto_parse_filename_metadata=bool(raw.get("auto_parse_filename_metadata", False)),
            filename_pattern=normalize_filename_pattern(raw.get("filename_pattern", DEFAULT_FILENAME_PATTERN)),
            has_header=bool(raw.get("has_header", True)),
            leading_rows_to_skip=max(0, int(raw.get("leading_rows_to_skip", 0) or 0)),
            trailing_rows_to_skip=max(0, int(raw.get("trailing_rows_to_skip", 0) or 0)),
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


def normalize_filename_pattern(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return DEFAULT_FILENAME_PATTERN
    return text.replace("{last8}", "{account_id}")
