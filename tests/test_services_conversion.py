from pathlib import Path
from types import SimpleNamespace

import pytest

from openstatement.models.profile import BankProfile
from openstatement.services.conversion import (
    extract_tag,
    format_ofx_date,
    format_preview,
    mapped_columns_missing,
    run_conversion,
    write_mapping_file,
)


def make_profile(*, split: bool = False) -> BankProfile:
    return BankProfile(
        name="SECU",
        headers=["date", "amount"],
        delimiter=",",
        field_map={"date": "Date", "amount": "Amount", "payee": "Payee"},
        debit_col="Debit",
        credit_col="Credit",
        use_split_amounts=split,
        date_format="%m/%d/%Y",
        dayfirst=True,
        account_type="CHECKING",
        account_id="secu",
        currency="USD",
    )


def test_mapped_columns_missing_non_split(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Amount\n2026-01-01,10\n", encoding="utf-8")

    missing = mapped_columns_missing(csv_path, make_profile(split=False))
    assert missing == ["Payee"]


def test_mapped_columns_missing_split(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Payee,Debit\n2026-01-01,Store,10\n", encoding="utf-8")

    missing = mapped_columns_missing(csv_path, make_profile(split=True))
    assert "Credit" in missing


def test_format_ofx_date_handles_multiple_shapes() -> None:
    assert format_ofx_date("20260102") == "2026-01-02"
    assert format_ofx_date("20260102112233[-5:EST]") == "2026-01-02"
    assert format_ofx_date("bad") == "bad"


def test_extract_tag_is_case_insensitive() -> None:
    block = "<name>Merchant"
    assert extract_tag(block, "NAME") == "Merchant"


def test_format_preview_with_transactions_and_truncation() -> None:
    ofx = "".join(
        [
            "<STMTTRN><DTPOSTED>20260101<TRNAMT>1.00<NAME>A<MEMO>X<FITID>1</STMTTRN>",
            "<STMTTRN><DTPOSTED>20260102<TRNAMT>2.00<NAME>B<MEMO>Y<FITID>2</STMTTRN>",
        ]
    )
    out = format_preview(ofx, max_rows=1)
    assert "Date" in out
    assert "Showing first 1 of 2 transactions." in out


def test_format_preview_fallback_for_non_stmttrn() -> None:
    raw = "<OFX>\nNO TRANSACTIONS\n"
    out = format_preview(raw)
    assert out.startswith("Could not parse transaction blocks")


def test_write_mapping_file_contains_expected_keys(tmp_path: Path) -> None:
    target = tmp_path / "mapping.py"
    write_mapping_file(target, make_profile(split=True))
    text = target.read_text(encoding="utf-8")
    assert "'amount': _split_amount" in text
    assert "'dayfirst': True" in text
    assert "'parse_fmt': '%m/%d/%Y'" in text


def test_run_conversion_raises_on_error(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    dest = tmp_path / "out.ofx"
    source.write_text("Date,Amount\n", encoding="utf-8")

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stderr="boom", stdout="")

    monkeypatch.setattr("openstatement.services.conversion.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="csv2ofx failed"):
        run_conversion("csv2ofx", source, dest, make_profile())


def test_run_conversion_success_invokes_subprocess(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    dest = tmp_path / "out.ofx"
    source.write_text("Date,Amount\n", encoding="utf-8")

    captured = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stderr="", stdout="ok")

    monkeypatch.setattr("openstatement.services.conversion.subprocess.run", fake_run)

    run_conversion("csv2ofx", source, dest, make_profile())
    assert captured["cmd"][0] == "csv2ofx"
    assert str(source) in captured["cmd"]
    assert str(dest) in captured["cmd"]
