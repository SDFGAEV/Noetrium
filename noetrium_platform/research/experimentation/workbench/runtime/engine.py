"""Pure standard-library execution for common paper data workflows."""
from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable
from statistics import median
from typing import Any

from noetrium_platform.foundation.kernel.kernel import canonical_digest, freeze_json
from ..api import (
    AggregationFunction, AggregationSpec, DataColumn, DataTable, GroupComparison,
    InferenceResult, MetricSummary, MissingValuePolicy, PairedComparison,
    SplitStrategy,
)


def _operation_sha(value: str) -> str:
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("operation configuration_digest must be lowercase SHA-256")
    return value


def _numeric(value: object, column: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"column {column!r} contains a non-finite numeric value")
    return float(value)


def _derived_table(table: DataTable, operation_id: str, configuration_digest: str,
                   columns: tuple[DataColumn, ...], rows: tuple[tuple[Any, ...], ...],
                   additional_lineage: tuple[str, ...] = ()) -> DataTable:
    if type(operation_id) is not str or not operation_id.strip():
        raise ValueError("operation_id must be non-empty")
    digest = _operation_sha(configuration_digest)
    metadata = tuple(item for item in table.metadata if item[0] != "last_operation") + (("last_operation", operation_id),)
    return DataTable(
        table.table_id,
        columns,
        rows,
        source_digest=table.source_digest,
        lineage_digests=tuple(dict.fromkeys(table.lineage_digests + (table.table_digest, digest) + additional_lineage)),
        metadata=metadata,
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
              operation_id: str, configuration_digest: str,
              strategy: SplitStrategy = SplitStrategy.RANDOM,
              stratify_by: tuple[str, ...] = (), group_by: tuple[str, ...] = (),
              order_by: tuple[str, ...] = ()) -> dict[str, DataTable]:
        if type(seed) is not int or isinstance(seed, bool):
            raise TypeError("split seed must be an integer")
        if not isinstance(strategy, SplitStrategy):
            raise TypeError("split strategy must be SplitStrategy")
        if type(fractions) is not tuple or not fractions or any(type(item) is not tuple or len(item) != 2 for item in fractions):
            raise TypeError("split fractions must be a tuple of name/fraction pairs")
        if len({item[0] for item in fractions}) != len(fractions) or any(type(name) is not str or not name.strip() for name, _ in fractions):
            raise ValueError("split names must be unique and non-empty")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0 for _, value in fractions):
            raise ValueError("split fractions must be positive finite numbers")
        if not math.isclose(sum(float(value) for _, value in fractions), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("split fractions must sum to 1")
        for label, names in (("stratify_by", stratify_by), ("group_by", group_by), ("order_by", order_by)):
            if type(names) is not tuple or any(type(name) is not str or not name.strip() for name in names):
                raise TypeError(f"split {label} must contain non-empty strings")
            if len(names) != len(set(names)):
                raise ValueError(f"split {label} must be unique")
            for name in names:
                table.column_index(name)
        if strategy is SplitStrategy.STRATIFIED and not stratify_by:
            raise ValueError("stratified split requires stratify_by")
        if strategy is SplitStrategy.GROUP and not group_by:
            raise ValueError("group split requires group_by")
        if strategy is SplitStrategy.TEMPORAL and not order_by:
            raise ValueError("temporal split requires order_by")
        rng = random.Random(seed)
        names = tuple(name for name, _ in fractions)
        weights = tuple(float(value) for _, value in fractions)

        def key(row: tuple[Any, ...], columns: tuple[str, ...]) -> tuple[str, ...]:
            return tuple(repr(freeze_json(row[table.column_index(name)])) for name in columns)

        def allocate(rows: list[tuple[Any, ...]], *, preserve_groups: bool = False, shuffle_rows: bool = True) -> list[list[tuple[Any, ...]]]:
            buckets: list[list[tuple[Any, ...]]] = [[] for _ in names]
            if preserve_groups:
                groups: dict[tuple[str, ...], list[tuple[Any, ...]]] = defaultdict(list)
                for row in rows:
                    groups.setdefault(key(row, group_by), []).append(row)
                units = list(groups.values())
                rng.shuffle(units)
                targets = [len(rows) * sum(weights[:index + 1]) for index in range(len(weights))]
                bucket_index = 0
                for unit in units:
                    if bucket_index < len(names) - 1 and len(buckets[bucket_index]) + len(unit) > targets[bucket_index]:
                        bucket_index += 1
                    buckets[bucket_index].extend(unit)
                return buckets
            if shuffle_rows:
                rng.shuffle(rows)
            start = 0
            for index, weight in enumerate(weights):
                end = len(rows) if index == len(weights) - 1 else start + round(len(rows) * weight)
                buckets[index].extend(rows[start:end])
                start = end
            return buckets

        if strategy is SplitStrategy.TEMPORAL:
            ordered = sorted(table.rows, key=lambda row: tuple(repr(freeze_json(row[table.column_index(name)])) for name in order_by))
            buckets = allocate(ordered, shuffle_rows=False)
        elif strategy is SplitStrategy.STRATIFIED:
            strata: dict[tuple[str, ...], list[tuple[Any, ...]]] = defaultdict(list)
            for row in table.rows:
                strata.setdefault(key(row, stratify_by), []).append(row)
            buckets = [[] for _ in names]
            for stratum in sorted(strata):
                local = allocate(strata[stratum])
                for index, rows in enumerate(local):
                    buckets[index].extend(rows)
        elif strategy is SplitStrategy.GROUP:
            buckets = allocate(list(table.rows), preserve_groups=True)
        else:
            buckets = allocate(list(table.rows))

        result: dict[str, DataTable] = {}
        split_config = canonical_digest({
            "operation_id": operation_id, "seed": seed, "fractions": fractions,
            "strategy": strategy.value, "stratify_by": stratify_by, "group_by": group_by,
            "order_by": order_by,
        })
        for name, rows in zip(names, buckets, strict=True):
            derived = _derived_table(table, f"{operation_id}:{name}", configuration_digest,
                                     table.columns, tuple(rows))
            split_digest = canonical_digest({"config": split_config, "name": name})
            result[name] = DataTable(
                derived.table_id + ":" + name, derived.columns, derived.rows,
                source_digest=derived.source_digest,
                lineage_digests=derived.lineage_digests + (split_digest,),
                metadata=derived.metadata + (("split_seed", str(seed)), ("split_strategy", strategy.value)),
            )
        return result

    def aggregate(self, table: DataTable, group_by: tuple[str, ...],
                  aggregations: tuple[AggregationSpec, ...], *,
                  operation_id: str, configuration_digest: str,
                  missing: MissingValuePolicy = MissingValuePolicy.SKIP) -> DataTable:
        if type(group_by) is not tuple or any(type(name) is not str or not name.strip() for name in group_by):
            raise TypeError("aggregate group_by must contain non-empty strings")
        if len(group_by) != len(set(group_by)):
            raise ValueError("aggregate group_by must be unique")
        if type(aggregations) is not tuple or not aggregations or any(type(item) is not AggregationSpec for item in aggregations):
            raise TypeError("aggregate aggregations must contain AggregationSpec")
        if type(missing) is not MissingValuePolicy:
            raise TypeError("aggregate missing must be MissingValuePolicy")
        group_indexes = tuple(table.column_index(name) for name in group_by)
        for spec in aggregations:
            if spec.source_column is not None:
                table.column_index(spec.source_column)
        grouped: dict[tuple[str, ...], list[tuple[Any, ...]]] = defaultdict(list)
        for row in table.rows:
            grouped[tuple(repr(freeze_json(row[index])) for index in group_indexes)].append(row)
        ordered_groups = sorted(grouped.items(), key=lambda item: item[0])
        columns = tuple(table.columns[table.column_index(name)] for name in group_by)
        output_columns = tuple(DataColumn(spec.output_name, spec.data_type, False) for spec in aggregations)
        output_rows: list[tuple[Any, ...]] = []
        for _, rows in ordered_groups:
            group_values = tuple(rows[0][index] for index in group_indexes)
            values: list[Any] = []
            for spec in aggregations:
                source_values = [row[table.column_index(spec.source_column)] for row in rows] if spec.source_column else list(rows)
                numeric = []
                for value in source_values:
                    if spec.function is AggregationFunction.COUNT:
                        continue
                    if value is None and missing is MissingValuePolicy.SKIP:
                        continue
                    numeric.append(_numeric(value, spec.source_column or spec.output_name))
                fn = spec.function
                if fn is AggregationFunction.COUNT:
                    values.append(len(rows))
                elif not numeric:
                    if missing is MissingValuePolicy.REJECT:
                        raise ValueError(f"aggregate column {spec.source_column!r} has no usable values")
                    values.append(None)
                elif fn is AggregationFunction.SUM:
                    values.append(sum(numeric))
                elif fn is AggregationFunction.MEAN:
                    values.append(sum(numeric) / len(numeric))
                elif fn is AggregationFunction.VARIANCE:
                    mean_value = sum(numeric) / len(numeric)
                    values.append(sum((value - mean_value) ** 2 for value in numeric) / (len(numeric) - 1) if len(numeric) > 1 else 0.0)
                elif fn is AggregationFunction.STANDARD_DEVIATION:
                    mean_value = sum(numeric) / len(numeric)
                    values.append(math.sqrt(sum((value - mean_value) ** 2 for value in numeric) / (len(numeric) - 1)) if len(numeric) > 1 else 0.0)
                elif fn is AggregationFunction.MINIMUM:
                    values.append(min(numeric))
                elif fn is AggregationFunction.MEDIAN:
                    values.append(median(numeric))
                elif fn is AggregationFunction.MAXIMUM:
                    values.append(max(numeric))
                else:
                    raise ValueError(f"unsupported aggregation function: {fn}")
            output_rows.append(group_values + tuple(values))
        return _derived_table(table, operation_id, configuration_digest,
                              columns + output_columns, tuple(output_rows))

    def join(self, left: DataTable, right: DataTable, on: tuple[str, ...], *,
             operation_id: str, configuration_digest: str, how: str = "inner") -> DataTable:
        if type(on) is not tuple or not on:
            raise ValueError("join keys must be a non-empty tuple")
        if type(how) is not str or how not in {"inner", "left"}:
            raise ValueError("join how must be inner or left")
        left_indexes = tuple(left.column_index(name) for name in on)
        right_indexes = tuple(right.column_index(name) for name in on)
        right_only = tuple((index, column) for index, column in enumerate(right.columns) if column.name not in on)
        if any(column.name in left.column_names for _, column in right_only):
            raise ValueError("join output columns must be unique")
        index: dict[tuple[str, ...], list[tuple[Any, ...]]] = defaultdict(list)
        for row in right.rows:
            index[tuple(repr(freeze_json(row[i])) for i in right_indexes)].append(row)
        columns = left.columns + tuple(column for _, column in right_only)
        rows: list[tuple[Any, ...]] = []
        for left_row in left.rows:
            matches = index.get(tuple(repr(freeze_json(left_row[i])) for i in left_indexes), [])
            if not matches and how == "left":
                rows.append(left_row + tuple(None for _ in right_only))
            for right_row in matches:
                rows.append(left_row + tuple(right_row[index] for index, _ in right_only))
        return _derived_table(left, operation_id, configuration_digest, columns, tuple(rows),
                              additional_lineage=(right.table_digest,))


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

    @staticmethod
    def _normal_p(value: float, standard_error: float) -> float | None:
        if standard_error == 0.0:
            return 0.0 if value != 0.0 else 1.0
        return math.erfc(abs(value / standard_error) / math.sqrt(2.0))

    @staticmethod
    def _quantile(values: list[float], probability: float) -> float:
        if not values:
            raise ValueError("quantile requires values")
        ordered = sorted(values)
        position = (len(ordered) - 1) * probability
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    def mean_inference(self, table: DataTable, value_column: str, *,
                       missing: MissingValuePolicy = MissingValuePolicy.REJECT) -> InferenceResult:
        values = [_numeric(value, value_column) for value in table.values(value_column)
                  if not (value is None and missing is MissingValuePolicy.SKIP)]
        if not values:
            raise ValueError("mean inference requires at least one numeric observation")
        estimate = sum(values) / len(values)
        variance = sum((value - estimate) ** 2 for value in values) / (len(values) - 1) if len(values) > 1 else 0.0
        standard_error = math.sqrt(variance / len(values))
        return InferenceResult(value_column, "normal_mean", len(values), estimate, standard_error,
                               estimate - 1.96 * standard_error, estimate + 1.96 * standard_error,
                               self._normal_p(estimate, standard_error), None, 0.0)

    def bootstrap_mean(self, table: DataTable, value_column: str, *,
                       replicates: int = 2000, seed: int = 0,
                       missing: MissingValuePolicy = MissingValuePolicy.REJECT) -> InferenceResult:
        if type(replicates) is not int or replicates < 100:
            raise ValueError("bootstrap replicates must be an integer of at least 100")
        values = [_numeric(value, value_column) for value in table.values(value_column)
                  if not (value is None and missing is MissingValuePolicy.SKIP)]
        if not values:
            raise ValueError("bootstrap requires at least one numeric observation")
        rng = random.Random(seed)
        estimates = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(replicates)]
        estimate = sum(values) / len(values)
        mean_estimate = sum(estimates) / len(estimates)
        variance = sum((value - mean_estimate) ** 2 for value in estimates) / (len(estimates) - 1)
        return InferenceResult(value_column, f"bootstrap_mean:{replicates}:{seed}", len(values),
                               estimate, math.sqrt(variance),
                               self._quantile(estimates, 0.025), self._quantile(estimates, 0.975),
                               None, None, 0.0)

    def paired_compare(self, table: DataTable, value_column: str, group_column: str, *,
                       pair_column: str, baseline: Any, candidate: Any,
                       missing: MissingValuePolicy = MissingValuePolicy.REJECT) -> PairedComparison:
        value_index = table.column_index(value_column)
        group_index = table.column_index(group_column)
        pair_index = table.column_index(pair_column)
        pairs: dict[Any, dict[Any, float]] = defaultdict(dict)
        for row in table.rows:
            value = row[value_index]
            if value is None and missing is MissingValuePolicy.SKIP:
                continue
            if row[group_index] not in (baseline, candidate):
                continue
            pair_key = repr(freeze_json(row[pair_index]))
            if row[group_index] in pairs[pair_key]:
                raise ValueError("paired comparison contains duplicate group values for one pair")
            pairs[pair_key][row[group_index]] = _numeric(value, value_column)
        differences = [values[candidate] - values[baseline] for values in pairs.values()
                       if baseline in values and candidate in values]
        if not differences:
            raise ValueError("paired comparison requires complete baseline/candidate pairs")
        estimate = sum(differences) / len(differences)
        variance = sum((value - estimate) ** 2 for value in differences) / (len(differences) - 1) if len(differences) > 1 else 0.0
        deviation = math.sqrt(variance)
        error = math.sqrt(variance / len(differences))
        return PairedComparison(value_column, pair_column, len(differences), estimate, deviation, error,
                                estimate - 1.96 * error, estimate + 1.96 * error,
                                self._normal_p(estimate, error),
                                estimate / deviation if deviation else None)

    def permutation_compare(self, table: DataTable, value_column: str, group_column: str, *,
                            baseline: Any, candidate: Any, replicates: int = 2000,
                            seed: int = 0,
                            missing: MissingValuePolicy = MissingValuePolicy.REJECT) -> InferenceResult:
        if type(replicates) is not int or replicates < 100:
            raise ValueError("permutation replicates must be an integer of at least 100")
        group_index = table.column_index(group_column)
        value_index = table.column_index(value_column)
        base = [_numeric(row[value_index], value_column) for row in table.rows
                if row[group_index] == baseline and not (row[value_index] is None and missing is MissingValuePolicy.SKIP)]
        cand = [_numeric(row[value_index], value_column) for row in table.rows
                if row[group_index] == candidate and not (row[value_index] is None and missing is MissingValuePolicy.SKIP)]
        if not base or not cand:
            raise ValueError("permutation comparison groups must each contain numeric observations")
        observed = sum(cand) / len(cand) - sum(base) / len(base)
        pooled = base + cand
        rng = random.Random(seed)
        exceedances = 0
        for _ in range(replicates):
            rng.shuffle(pooled)
            candidate_sample = pooled[:len(cand)]
            baseline_sample = pooled[len(cand):]
            permuted = sum(candidate_sample) / len(candidate_sample) - sum(baseline_sample) / len(baseline_sample)
            exceedances += abs(permuted) >= abs(observed)
        p_value = (exceedances + 1) / (replicates + 1)
        return InferenceResult(value_column, f"permutation_difference:{replicates}:{seed}",
                               len(base) + len(cand), observed, 0.0, observed, observed,
                               p_value, None, 0.0)


__all__ = ["ScientificStatistics", "TablePipeline"]