"""Structured, read-only DuckDB analytics for CSV and Parquet outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
from crewai.tools import BaseTool

from config import OUTPUT_DIR

_ALLOWED_KEYS = {"path", "aggregate", "value", "group_by", "limit", "output_csv"}
_AGGREGATES = {"count", "sum", "avg", "min", "max"}
_MAX_ROWS = 500


def _parse_payload(input_str: str) -> dict[str, Any]:
    payload = json.loads(input_str)
    if not isinstance(payload, dict):
        raise ValueError("Input harus JSON object.")
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(f"Field tidak diizinkan: {', '.join(sorted(unknown))}")
    return payload


def _resolve_source(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("path wajib diisi.")
    root = Path(OUTPUT_DIR).resolve()
    candidate = Path(raw_path.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    source = candidate.resolve()
    if source != root and root not in source.parents:
        raise ValueError("File harus berada di dalam outputs.")
    if source.suffix.lower() not in {".csv", ".parquet"}:
        raise ValueError("Format file harus CSV atau Parquet.")
    if not source.is_file():
        raise ValueError(f"File tidak ditemukan: {source}")
    return source


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _require_column(raw: Any, columns: list[str], field: str) -> str:
    if not isinstance(raw, str) or raw not in columns:
        raise ValueError(f"{field} tidak ditemukan di schema file.")
    return raw


def _output_target(raw_name: Any) -> Path | None:
    if raw_name in (None, ""):
        return None
    if not isinstance(raw_name, str):
        raise ValueError("output_csv harus string.")
    clean = raw_name.strip()
    if Path(clean).name != clean or Path(clean).suffix.lower() != ".csv":
        raise ValueError("output_csv harus nama file .csv tanpa folder.")
    target = (Path(OUTPUT_DIR).resolve() / clean).resolve()
    if target.exists():
        raise FileExistsError(f"File output sudah ada: {target.name}")
    return target


class DuckDBAnalysisTool(BaseTool):
    name: str = "DuckDB CSV Parquet Analyzer"
    description: str = (
        "Analisis read-only CSV/Parquet di outputs dengan agregasi aman. Input JSON: "
        '{"path":"/path/outputs/data.csv","aggregate":"count|sum|avg|min|max",'
        '"value":"kolom_angka","group_by":"kolom_grup","limit":100,'
        '"output_csv":"ringkasan.csv"}. count tidak membutuhkan value. Raw SQL ditolak.'
    )

    def _run(self, input_str: str) -> str:
        try:
            payload = _parse_payload(input_str)
            source = _resolve_source(payload.get("path"))
            aggregate = payload.get("aggregate")
            if aggregate not in _AGGREGATES:
                raise ValueError("aggregate harus count, sum, avg, min, atau max.")
            limit = payload.get("limit", 100)
            if not isinstance(limit, int) or not 1 <= limit <= _MAX_ROWS:
                raise ValueError(f"limit harus 1-{_MAX_ROWS}.")

            relation = (
                duckdb.read_csv(str(source), header=True)
                if source.suffix.lower() == ".csv"
                else duckdb.read_parquet(str(source))
            )
            source_columns = list(relation.columns)
            group_by = payload.get("group_by")
            group_expression = None
            if group_by not in (None, ""):
                group_by = _require_column(group_by, source_columns, "group_by")
                group_expression = _quote_identifier(group_by)

            if aggregate == "count":
                aggregate_expression = 'count(*) AS "value"'
            else:
                value = _require_column(payload.get("value"), source_columns, "value")
                aggregate_expression = (
                    f'{aggregate}({_quote_identifier(value)}) AS "value"'
                )

            if group_expression:
                selected = f"{group_expression}, {aggregate_expression}"
                result = relation.aggregate(selected, group_expression).limit(limit)
            else:
                result = relation.aggregate(aggregate_expression).limit(limit)
            output_csv = _output_target(payload.get("output_csv"))
            if output_csv is not None:
                result.write_csv(str(output_csv), header=True)

            response = {
                "source": str(source),
                "columns": list(result.columns),
                "rows": [list(row) for row in result.fetchall()],
            }
            if output_csv is not None:
                response["output_csv"] = str(output_csv)
            return "SUCCESS|" + json.dumps(response, ensure_ascii=False, default=str)
        except (duckdb.Error, json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            return f"FAILED|{exc}"
