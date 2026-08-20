from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from openstatement.models.profile import BankProfile
from openstatement.services.conversion import (
    CSV2OFX_MODULE_RUNNER,
    CsvPreprocessingError,
    OfxMetadataOverrides,
    apply_ofx_overrides,
    compute_effective_rows,
    effective_source_csv,
    extract_tag,
    find_csv2ofx_binary,
    format_ofx_date,
    format_preview,
    latest_transaction_date,
    mapped_columns_missing,
    run_conversion,
    suggested_export_filename,
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
        has_header=True,
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
    assert "'has_header': True" in text
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


def test_write_mapping_file_no_header_uses_csv2ofx_column_names(tmp_path: Path) -> None:
    target = tmp_path / "mapping.py"
    profile = make_profile(split=False)
    profile.has_header = False
    profile.field_map = {"date": "col_1", "amount": "col_2", "payee": "col_3"}
    write_mapping_file(target, profile)
    text = target.read_text(encoding="utf-8")
    assert "'has_header': False" in text
    assert "itemgetter('column_1')" in text
    assert "record.get('column_2'" in text
    assert "itemgetter('column_3')" in text


def test_mapped_columns_missing_no_header_uses_generated_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("2026-01-01,10,Store\n2026-01-02,11,Cafe\n", encoding="utf-8")

    profile = make_profile(split=False)
    profile.has_header = False
    profile.field_map = {"date": "col_1", "amount": "col_2", "payee": "col_3"}

    missing = mapped_columns_missing(csv_path, profile)
    assert missing == []


def test_compute_effective_rows_zero_zero_returns_all_rows() -> None:
    rows = [["Date", "Amount"], ["2026-01-01", "10"]]
    assert compute_effective_rows(rows, make_profile()) == rows


def test_compute_effective_rows_leading_and_trailing() -> None:
    rows = [
        ["Bank Statement"],
        ["Account 123"],
        ["Date", "Amount"],
        ["2026-01-01", "10"],
        ["2026-01-02", "20"],
        ["Ending Balance", "30"],
    ]
    profile = make_profile()
    profile.leading_rows_to_skip = 2
    profile.trailing_rows_to_skip = 1

    effective = compute_effective_rows(rows, profile)
    assert effective == [["Date", "Amount"], ["2026-01-01", "10"], ["2026-01-02", "20"]]


def test_compute_effective_rows_leading_only_no_header() -> None:
    rows = [["Bank Statement"], ["Account 123"], ["2026-01-01", "Coffee", "-5.00"]]
    profile = make_profile()
    profile.has_header = False
    profile.leading_rows_to_skip = 2

    assert compute_effective_rows(rows, profile) == [["2026-01-01", "Coffee", "-5.00"]]


def test_compute_effective_rows_all_removed_with_header_raises_clear_error() -> None:
    rows = [["a"], ["b"], ["c"]]
    profile = make_profile()
    profile.has_header = True
    profile.leading_rows_to_skip = 2
    profile.trailing_rows_to_skip = 2

    with pytest.raises(CsvPreprocessingError, match="header row"):
        compute_effective_rows(rows, profile)


def test_compute_effective_rows_all_removed_without_header_raises_clear_error() -> None:
    rows = [["a"], ["b"]]
    profile = make_profile()
    profile.has_header = False
    profile.leading_rows_to_skip = 5

    with pytest.raises(CsvPreprocessingError):
        compute_effective_rows(rows, profile)


def test_compute_effective_rows_trailing_greater_than_available_rows_raises() -> None:
    rows = [["a"], ["b"]]
    profile = make_profile()
    profile.trailing_rows_to_skip = 10

    with pytest.raises(CsvPreprocessingError):
        compute_effective_rows(rows, profile)


def test_effective_source_csv_returns_original_path_when_no_skip(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("Date,Amount\n2026-01-01,10\n", encoding="utf-8")

    with effective_source_csv(source, make_profile()) as effective:
        assert effective == source


def test_effective_source_csv_trims_leading_and_trailing_rows(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text(
        "Bank Statement\nDate,Amount\n2026-01-01,10\n2026-01-02,20\nEnding Balance,30\n",
        encoding="utf-8",
    )
    profile = make_profile()
    profile.leading_rows_to_skip = 1
    profile.trailing_rows_to_skip = 1

    with effective_source_csv(source, profile) as effective:
        assert effective != source
        content = effective.read_text(encoding="utf-8")

    assert "Bank Statement" not in content
    assert "Ending Balance" not in content
    assert "Date,Amount" in content
    assert "2026-01-02,20" in content


def test_effective_source_csv_raises_clean_error_when_all_rows_removed(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("a\nb\nc\n", encoding="utf-8")
    profile = make_profile()
    profile.leading_rows_to_skip = 3
    profile.trailing_rows_to_skip = 2

    with pytest.raises(CsvPreprocessingError):
        with effective_source_csv(source, profile):
            pass


def test_mapped_columns_missing_uses_effective_header_after_leading_skip(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text(
        "Account Summary\nDate,Amount,Payee\n2026-01-01,10,Store\n", encoding="utf-8"
    )
    profile = make_profile(split=False)
    profile.leading_rows_to_skip = 1

    assert mapped_columns_missing(csv_path, profile) == []


def test_mapped_columns_missing_returns_error_message_when_all_rows_skipped(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Amount\n2026-01-01,10\n", encoding="utf-8")
    profile = make_profile()
    profile.leading_rows_to_skip = 5

    missing = mapped_columns_missing(csv_path, profile)
    assert len(missing) == 1
    assert "row skip settings" in missing[0]


def test_latest_transaction_date_picks_max_date_with_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text(
        "Date,Amount,Payee\n01/05/2026,10,A\n01/20/2026,20,B\n01/10/2026,15,C\n",
        encoding="utf-8",
    )
    latest = latest_transaction_date(csv_path, make_profile())
    assert latest == datetime(2026, 1, 20)


def test_latest_transaction_date_headerless_uses_col_index(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("01/05/2026,10,A\n01/20/2026,20,B\n", encoding="utf-8")

    profile = make_profile()
    profile.has_header = False
    profile.field_map = {"date": "col_1", "amount": "col_2", "payee": "col_3"}

    latest = latest_transaction_date(csv_path, profile)
    assert latest == datetime(2026, 1, 20)


def test_latest_transaction_date_respects_leading_and_trailing_skip(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text(
        "Junk Metadata\nDate,Amount,Payee\n01/05/2026,10,A\n01/20/2026,20,B\nTotals,,\n",
        encoding="utf-8",
    )
    profile = make_profile()
    profile.leading_rows_to_skip = 1
    profile.trailing_rows_to_skip = 1

    latest = latest_transaction_date(csv_path, profile)
    assert latest == datetime(2026, 1, 20)


def test_latest_transaction_date_returns_none_when_unparseable(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Amount,Payee\nn/a,10,A\nn/a,20,B\n", encoding="utf-8")

    latest = latest_transaction_date(csv_path, make_profile())
    assert latest is None


def test_latest_transaction_date_uses_dateutil_when_no_date_format(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Amount,Payee\n2026-01-05,10,A\n2026-01-20,20,B\n", encoding="utf-8")

    profile = make_profile()
    profile.date_format = ""
    profile.dayfirst = False

    latest = latest_transaction_date(csv_path, profile)
    assert latest == datetime(2026, 1, 20)


def test_suggested_export_filename_builds_expected_name(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text(
        "Date,Amount,Payee\n01/05/2026,10,A\n01/20/2026,20,B\n", encoding="utf-8"
    )
    assert suggested_export_filename(csv_path, make_profile()) == "SECU_secu_2026-01-20.ofx"


def test_suggested_export_filename_sanitizes_invalid_characters(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Amount,Payee\n01/05/2026,10,A\n", encoding="utf-8")

    profile = make_profile()
    profile.name = "SECU/Checking:Primary"
    profile.account_id = "secu"

    name = suggested_export_filename(csv_path, profile)
    assert "/" not in name
    assert ":" not in name
    assert name == "SECU_Checking_Primary_secu_2026-01-05.ofx"


def test_suggested_export_filename_omits_date_when_none_found(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Amount,Payee\n", encoding="utf-8")

    assert suggested_export_filename(csv_path, make_profile()) == "SECU_secu.ofx"


def test_suggested_export_filename_falls_back_account_id_when_blank(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text("Date,Amount,Payee\n01/05/2026,10,A\n", encoding="utf-8")

    profile = make_profile()
    profile.account_id = ""

    name = suggested_export_filename(csv_path, profile)
    assert name == "SECU_secu_2026-01-05.ofx"


def test_run_conversion_zero_zero_uses_source_path_directly(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    dest = tmp_path / "out.ofx"
    source.write_text("Date,Amount\n2026-01-01,10\n", encoding="utf-8")

    captured = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stderr="", stdout="ok")

    monkeypatch.setattr("openstatement.services.conversion.subprocess.run", fake_run)

    run_conversion("csv2ofx", source, dest, make_profile())
    assert str(source) in captured["cmd"]


def test_run_conversion_trims_rows_before_invoking_csv2ofx(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text(
        "Bank Statement\nDate,Amount\n2026-01-01,10\n2026-01-02,20\nEnding Balance,30\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out.ofx"
    captured = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        o_index = cmd.index("-o")
        effective_path = Path(cmd[o_index + 1])
        captured["content"] = effective_path.read_text(encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="", stdout="ok")

    monkeypatch.setattr("openstatement.services.conversion.subprocess.run", fake_run)

    profile = make_profile()
    profile.leading_rows_to_skip = 1
    profile.trailing_rows_to_skip = 1

    run_conversion("csv2ofx", source, dest, profile)

    assert str(source) not in captured["cmd"]
    assert "Bank Statement" not in captured["content"]
    assert "Ending Balance" not in captured["content"]
    assert "2026-01-02,20" in captured["content"]


def test_run_conversion_raises_clean_error_when_row_skip_removes_everything(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "in.csv"
    source.write_text("a\nb\nc\n", encoding="utf-8")
    dest = tmp_path / "out.ofx"

    def fake_run(*_args, **_kwargs):  # pragma: no cover - should not be called
        raise AssertionError("csv2ofx should not run when preprocessing fails")

    monkeypatch.setattr("openstatement.services.conversion.subprocess.run", fake_run)

    profile = make_profile()
    profile.leading_rows_to_skip = 3
    profile.trailing_rows_to_skip = 2

    with pytest.raises(CsvPreprocessingError):
        run_conversion("csv2ofx", source, dest, profile)


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
