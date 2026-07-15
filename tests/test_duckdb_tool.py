import importlib
import importlib.util
import json
from pathlib import Path

import pytest


def _module():
    assert importlib.util.find_spec("teams.t4_admin.duckdb_tool") is not None
    return importlib.import_module("teams.t4_admin.duckdb_tool")


def _csv(outputs: Path) -> Path:
    path = outputs / "sales.csv"
    path.write_text(
        "category,value\nchair,10\nchair,20\ntable,5\n", encoding="utf-8"
    )
    return path


def _payload(result: str) -> dict:
    assert result.startswith("SUCCESS|")
    return json.loads(result.removeprefix("SUCCESS|"))


def test_duckdb_groups_csv_and_writes_derived_csv(tmp_path, monkeypatch):
    module = _module()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    source = _csv(outputs)
    monkeypatch.setattr(module, "OUTPUT_DIR", outputs)

    result = module.DuckDBAnalysisTool()._run(
        json.dumps(
            {
                "path": str(source),
                "aggregate": "sum",
                "value": "value",
                "group_by": "category",
                "output_csv": "sales_summary.csv",
            }
        )
    )

    payload = _payload(result)
    assert payload["columns"] == ["category", "value"]
    assert {tuple(row) for row in payload["rows"]} == {
        ("chair", 30),
        ("table", 5),
    }
    derived = outputs / "sales_summary.csv"
    assert payload["output_csv"] == str(derived)
    assert derived.exists()


@pytest.mark.parametrize(
    ("aggregate", "expected"),
    [("count", 3), ("sum", 35), ("avg", pytest.approx(35 / 3)), ("min", 5), ("max", 20)],
)
def test_duckdb_allows_only_supported_aggregates(
    tmp_path, monkeypatch, aggregate, expected
):
    module = _module()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    source = _csv(outputs)
    monkeypatch.setattr(module, "OUTPUT_DIR", outputs)
    request = {"path": str(source), "aggregate": aggregate}
    if aggregate != "count":
        request["value"] = "value"

    payload = _payload(module.DuckDBAnalysisTool()._run(json.dumps(request)))

    assert payload["rows"][0][0] == expected


def test_duckdb_reads_parquet(tmp_path, monkeypatch):
    module = _module()
    import duckdb

    outputs = tmp_path / "outputs"
    outputs.mkdir()
    source = outputs / "sales.parquet"
    duckdb.sql(
        "SELECT * FROM (VALUES ('chair', 10), ('table', 5)) "
        "AS sales(category, value)"
    ).write_parquet(str(source))
    monkeypatch.setattr(module, "OUTPUT_DIR", outputs)

    payload = _payload(
        module.DuckDBAnalysisTool()._run(
            json.dumps({"path": str(source), "aggregate": "max", "value": "value"})
        )
    )

    assert payload["rows"] == [[10]]


def test_duckdb_rejects_outside_path_suffix_operation_and_raw_sql(
    tmp_path, monkeypatch
):
    module = _module()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    source = _csv(outputs)
    outside = tmp_path / "outside.csv"
    outside.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    invalid = outputs / "data.xlsx"
    invalid.write_text("x", encoding="utf-8")
    monkeypatch.setattr(module, "OUTPUT_DIR", outputs)
    tool = module.DuckDBAnalysisTool()

    requests = [
        {"path": str(outside), "aggregate": "count"},
        {"path": str(invalid), "aggregate": "count"},
        {"path": str(source), "aggregate": "median", "value": "value"},
        {"path": str(source), "aggregate": "count", "sql": "SELECT *"},
    ]

    assert all(tool._run(json.dumps(request)).startswith("FAILED|") for request in requests)


def test_duckdb_rejects_unknown_column_and_caps_limit(tmp_path, monkeypatch):
    module = _module()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    source = _csv(outputs)
    monkeypatch.setattr(module, "OUTPUT_DIR", outputs)
    tool = module.DuckDBAnalysisTool()

    unknown = tool._run(
        json.dumps({"path": str(source), "aggregate": "sum", "value": "password"})
    )
    too_large = tool._run(
        json.dumps({"path": str(source), "aggregate": "count", "limit": 501})
    )

    assert unknown.startswith("FAILED|")
    assert too_large.startswith("FAILED|")


def test_duckdb_returns_failure_for_invalid_aggregate_type(tmp_path, monkeypatch):
    module = _module()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    source = outputs / "labels.csv"
    source.write_text("label\nchair\ntable\n", encoding="utf-8")
    monkeypatch.setattr(module, "OUTPUT_DIR", outputs)

    result = module.DuckDBAnalysisTool()._run(
        json.dumps({"path": str(source), "aggregate": "sum", "value": "label"})
    )

    assert result.startswith("FAILED|")
