from pathlib import Path
from types import SimpleNamespace

import pytest

from openstatement.models.profile import BankProfile
from openstatement.services.conversion import (
    CSV2OFX_MODULE_RUNNER,
    OfxMetadataOverrides,
    apply_ofx_overrides,
    extract_tag,
    find_csv2ofx_binary,
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
        auto_parse_filename_metadata=False,
        filename_pattern="{account_name}_{last8}_{statement_date}_{ending_balance}.csv",
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


def test_write_mapping_file_non_split_amount_parser_handles_blank_and_currency(tmp_path: Path) -> None:
    target = tmp_path / "mapping.py"
    write_mapping_file(target, make_profile(split=False))

    namespace: dict[str, object] = {}
    exec(target.read_text(encoding="utf-8"), namespace)  # noqa: S102
    amount_fn = namespace["mapping"]["amount"]

    assert amount_fn({"Amount": ""}) == 0.0
    assert amount_fn({"Amount": "$1,234.56"}) == 1234.56


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


def test_run_conversion_module_runner_invokes_module_path(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    dest = tmp_path / "out.ofx"
    source.write_text("Date,Amount\n", encoding="utf-8")

    captured = {}

    def fake_run(args):
        captured["args"] = args

    monkeypatch.setattr("openstatement.services.conversion._run_csv2ofx_module", fake_run)

    run_conversion(CSV2OFX_MODULE_RUNNER, source, dest, make_profile())
    assert captured["args"][0] == "-x"
    assert str(source) in captured["args"]
    assert str(dest) in captured["args"]


def test_find_csv2ofx_binary_falls_back_to_module_runner(monkeypatch) -> None:
    monkeypatch.setattr("openstatement.services.conversion.shutil.which", lambda _name: None)
    monkeypatch.setattr("openstatement.services.conversion.importlib.util.find_spec", lambda _name: object())
    assert find_csv2ofx_binary() == CSV2OFX_MODULE_RUNNER


def test_apply_ofx_overrides_sets_missing_values(tmp_path: Path) -> None:
    target = tmp_path / "out.ofx"
    target.write_text(
        "<OFX><STMTRS><BANKACCTFROM></BANKACCTFROM><BANKTRANLIST></BANKTRANLIST></STMTRS></OFX>",
        encoding="utf-8",
    )

    apply_ofx_overrides(
        target,
        OfxMetadataOverrides(
            account_id="31676003",
            statement_date="2026-04-24",
            ending_balance="1520.44",
        ),
    )
    out = target.read_text(encoding="utf-8")
    assert "<ACCTID>31676003" in out
    assert "<BALAMT>1520.44" in out
    assert "<DTASOF>20260424" in out


def test_apply_ofx_overrides_preserves_existing_values(tmp_path: Path) -> None:
    target = tmp_path / "out.ofx"
    target.write_text(
        (
            "<OFX><STMTRS><BANKACCTFROM><ACCTID>existing</ACCTID></BANKACCTFROM>"
            "<LEDGERBAL><BALAMT>44.00<DTASOF>20260101</LEDGERBAL></STMTRS></OFX>"
        ),
        encoding="utf-8",
    )

    apply_ofx_overrides(
        target,
        OfxMetadataOverrides(
            account_id="31676003",
            statement_date="2026-04-24",
            ending_balance="1520.44",
        ),
    )
    out = target.read_text(encoding="utf-8")
    assert "<ACCTID>existing" in out
    assert "<BALAMT>44.00" in out
    assert "<DTASOF>20260101" in out
