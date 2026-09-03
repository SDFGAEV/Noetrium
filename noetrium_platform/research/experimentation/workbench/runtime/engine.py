"""Pure standard-library execution for common paper data workflows."""
from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable
from statistics import median
from typing import Any

from noetrium_platform.foundation.kernel.kernel import canonical_digest, freeze_json
from ..api import DataColumn, DataTable, GroupComparison, MetricSummary, MissingValuePolicy


def _operation_sha(value: str) -> str:
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("operation configuration_digest must be lowercase SHA-256")
    return value


def _numeric(value: object, column: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"column {column!r} contains a non-finite numeric value")
    return float(value)


def _derived_table(table: DataTable, operation_id: str, configuration_digest: str,
                   columns: tuple[DataColumn, ...], rows: tuple[tuple[Any, ...], ...]) -> DataTable:
    if type(operation_id) is not str or not operation_id.strip():
        raise ValueError("operation_id must be non-empty")
    digest = _operation_sha(configuration_digest)
    return DataTable(
        table.table_id,
        columns,
        rows,
        source_digest=table.source_digest,
        lineage_digests=tuple(dict.fromkeys(table.lineage_digests + (table.table_digest, digest))),
        metadata=table.metadata + (("last_operation", operation_id),),
    )


class TablePipeline:
    """Composable transformations with explicit implementation/configuration lineage."""

    def project(self, table: DataTable, columns: tuple[str, ...], *,
                operation_id: str, configuration_digest: str) -> DataTable:
        if type(columns) is not tuple or not columns or len(set(columns)) != len(columns):
            raise ValueError("project columns must be a non-empty unique tuple")
        indexes = tuple(table.column_index(name) for name in columns)
        schema = tuple(table.columns[index] for index in indexes)
        rows = tuple(tuple(row[index] for index in indexes) for row in table.rows)
        return _derived_table(table, operation_id, configuration_digest, schema, rows)

    def filter(self, table: DataTable, predicate: Callable[[dict[str, Any]], bool], *,
               operation_id: str, configuration_digest: str) -> DataTable:
        if not callable(predicate):
            raise TypeError("filter predicate must be callable")
        names = table.column_names
        rows = tuple(row for row in table.rows if predicate(dict(zip(names, row, strict=True))))
        return _derived_table(table, operation_id, configuration_digest, table.columns, rows)

    def derive(self, table: DataTable, column: DataColumn, function: Callable[[dict[str, Any]], Any], *,
               operation_id: str, configuration_digest: str) -> DataTable:
        if type(column) is not DataColumn or not callable(function):
            raise TypeError("derive requires DataColumn and callable function")
        if column.name in table.column_names:
            raise ValueError(f"derived column already exists: {column.name}")
        names = table.column_names
        rows = tuple(row + (freeze_json(function(dict(zip(names, row, strict=True)))),) for row in table.rows)
        return _derived_table(table, operation_id, configuration_digest, table.columns + (column,), rows)

    def split(self, table: DataTable, *, seed: int, fractions: tuple[tuple[str, float], ...],
              operation_id: str, configuration_digest: str) -> dict[str, DataTable]:
        if type(seed) is not int or isinstance(seed, bool):
            raise TypeError("split seed must be an integer")
        if type(fractions) is not tuple or not fractions or any(type(item) is not tuple or len(item) != 2 for item in fractions):
            raise TypeError("split fractions must be a tuple of name/fraction pairs")
        if len({item[0] for item in fractions}) != len(fractions) or any(not name.strip() for name, _ in fractions):
            raise ValueError("split names must be unique and non-empty")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0 for _, value in fractions):
            raise ValueError("split fractions must be positive numbers")
        total = sum(float(value) for _, value in fractions)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("split fractions must sum to 1")
        shuffled = list(table.rows)
        random.Random(seed).shuffle(shuffled)
        result: dict[str, DataTable] = {}
        start = 0
        for index, (name, fraction) in enumerate(fractions):
            end = len(shuffled) if index == len(fractions) - 1 else start + round(len(shuffled) * float(fraction))
            split_digest = canonical_digest({"seed": seed, "name": name, "fraction": fraction})
            result[name] = _derived_table(table, f"{operation_id}:{name}", configuration_digest,
                                           table.columns, tuple(shuffled[start:end]))
            result[name] = DataTable(result[name].table_id + ":" + name, result[name].columns, result[name].rows,
                                     source_digest=result[name].source_digest,
                                     lineage_digests=result[name].lineage_digests + (split_digest,),
                                     metadata=result[name].metadata + (("split_seed", str(seed)),))
            start = end
        return result


class ScientificStatistics:
    """One shared numeric analysis authority for summaries and two-group effects."""

    def summarize(self, table: DataTable, value_column: str, *,
                  group_by: tuple[str, ...] = (),
                  missing: MissingValuePolicy = MissingValuePolicy.REJECT) -> tuple[MetricSummary, ...]:
        if type(missing) is not MissingValuePolicy:
            raise TypeError("missing must be MissingValuePolicy")
        value_index = table.column_index(value_column)
        group_indexes = tuple(table.column_index(name) for name in group_by)
        grouped: dict[str, tuple[tuple[str, Any], list[float]]] = {}
        for row in table.rows:
            value = row[value_index]
            if value is None and missing is MissingValuePolicy.SKIP:
                continue
            numeric = _numeric(value, value_column)
            group = tuple((name, freeze_json(row[index])) for name, index in zip(group_by, group_indexes, strict=True))
            key = canonical_digest(group)
            grouped.setdefault(key, (group, []))[1].append(numeric)
        summaries = []
        for group, values in sorted(grouped.values(), key=lambda item: repr(item[0])):
            ordered = sorted(values)
            count = len(ordered)
            mean = sum(ordered) / count
            variance = sum((value - mean) ** 2 for value in ordered) / (count - 1) if count > 1 else 0.0
            deviation = math.sqrt(variance)
            error = math.sqrt(variance / count)
            margin = 1.96 * error
            summaries.append(MetricSummary(value_column, group, count, mean, variance, deviation, error,
                                           ordered[0], median(ordered), ordered[-1], mean - margin, mean + margin))
        return tuple(summaries)

    def compare(self, table: DataTable, value_column: str, group_column: str, *,
                baseline: Any, candidate: Any,
                missing: MissingValuePolicy = MissingValuePolicy.REJECT) -> GroupComparison:
        group_index = table.column_index(group_column)
        value_index = table.column_index(value_column)
        base: list[float] = []
        cand: list[float] = []
        for row in table.rows:
            if row[group_index] == baseline:
                if row[value_index] is None and missing is MissingValuePolicy.SKIP:
                    continue
                base.append(_numeric(row[value_index], value_column))
            elif row[group_index] == candidate:
                if row[value_index] is None and missing is MissingValuePolicy.SKIP:
                    continue
                cand.append(_numeric(row[value_index], value_column))
        if not base or not cand:
            raise ValueError("comparison groups must each contain at least one numeric observation")
        base_mean = sum(base) / len(base)
        cand_mean = sum(cand) / len(cand)
        difference = cand_mean - base_mean
        base_var = sum((x - base_mean) ** 2 for x in base) / (len(base) - 1) if len(base) > 1 else 0.0
        cand_var = sum((x - cand_mean) ** 2 for x in cand) / (len(cand) - 1) if len(cand) > 1 else 0.0
        standard_error = math.sqrt(base_var / len(base) + cand_var / len(cand))
        pooled_n = len(base) + len(cand) - 2
        pooled = math.sqrt(((len(base) - 1) * base_var + (len(cand) - 1) * cand_var) / pooled_n) if pooled_n else 0.0
        return GroupComparison(value_column, group_column, freeze_json(baseline), freeze_json(candidate),
                               len(base), len(cand), difference,
                               difference / base_mean if base_mean else None,
                               difference / pooled if pooled else None,
                               difference - 1.96 * standard_error, difference + 1.96 * standard_error)


__all__ = ["ScientificStatistics", "TablePipeline"]