from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from noetrium.contracts.research import (
    DataColumn, DataTable, FigureKind, FigurePoint, FigureSeries, FigureSpec,
    MissingValuePolicy, ScientificStatistics, StandardTableRenderer,
    SvgFigureRenderer, TablePipeline,
)
from noetrium_platform.research.workbench.providers import CsvTableReader


SHA_A = "a" * 64
SHA_B = "b" * 64


def _table() -> DataTable:
    return DataTable(
        "scores",
        (DataColumn("variant", "text", False), DataColumn("score", "float", False), DataColumn("step", "int", False)),
        (("control", 1.0, 0), ("control", 3.0, 1), ("treatment", 4.0, 0), ("treatment", 8.0, 1)),
        source_digest=SHA_A,
    )


def test_table_is_immutable_and_binds_schema_rows_and_lineage():
    table = _table()
    assert table.column_names == ("variant", "score", "step")
    assert table.values("score") == (1.0, 3.0, 4.0, 8.0)
    assert len(table.table_digest) == 64


def test_pipeline_transforms_require_configuration_and_split_is_replayable():
    table = _table()
    pipeline = TablePipeline()
    derived = pipeline.derive(
        table, DataColumn("weighted", "float", False),
        lambda row: row["score"] * 2,
        operation_id="score.weight",
        configuration_digest=SHA_B,
    )
    assert derived.values("weighted") == (2.0, 6.0, 8.0, 16.0)
    first = pipeline.split(table, seed=17, fractions=(("train", 0.5), ("test", 0.5)),
                           operation_id="split", configuration_digest=SHA_B)
    second = pipeline.split(table, seed=17, fractions=(("train", 0.5), ("test", 0.5)),
                            operation_id="split", configuration_digest=SHA_B)
    assert first["train"].rows == second["train"].rows
    assert first["test"].table_digest == second["test"].table_digest


def test_scientific_statistics_centralizes_summary_effect_and_missing_policy():
    table = _table()
    stats = ScientificStatistics()
    summaries = stats.summarize(table, "score", group_by=("variant",))
    assert [(row.group, row.count, row.mean) for row in summaries] == [
        ((("variant", "control"),), 2, 2.0),
        ((("variant", "treatment"),), 2, 6.0),
    ]
    comparison = stats.compare(table, "score", "variant", baseline="control", candidate="treatment")
    assert comparison.difference == 4.0
    assert comparison.standardized_effect > 0
    nullable = DataTable("nullable", (DataColumn("score", "float"),), ((1.0,), (None,)))
    assert stats.summarize(nullable, "score", missing=MissingValuePolicy.SKIP)[0].count == 1


def test_standard_outputs_are_backend_neutral():
    table = _table()
    csv_text = StandardTableRenderer().render(table, "csv")
    markdown = StandardTableRenderer().render(table, "markdown")
    assert csv_text.splitlines()[0] == "variant,score,step"
    assert "| variant | score | step |" in markdown
    figure = FigureSpec("scores", "Scores by step", FigureKind.LINE, (
        FigureSeries("control", (FigurePoint(0, 1.0), FigurePoint(1, 3.0))),
        FigureSeries("treatment", (FigurePoint(0, 4.0), FigurePoint(1, 8.0))),
    ), y_label="score")
    svg = SvgFigureRenderer().render(figure)
    assert svg.startswith("<svg ")
    assert "Scores by step" in svg
    assert hashlib.sha256(svg.encode()).hexdigest() == hashlib.sha256(SvgFigureRenderer().render(figure).encode()).hexdigest()


def test_csv_reader_pins_source_digest_and_numeric_coercion():
    with tempfile.TemporaryDirectory(dir=".") as folder:
        source = Path(folder) / "scores.csv"
        source.write_text("variant,score\ncontrol,1.5\ntreatment,2.5\n", encoding="utf-8")
        table = CsvTableReader(coerce_numeric=True).read(str(source), table_id="csv-scores")
        assert table.values("score") == (1.5, 2.5)
        assert table.source_digest == hashlib.sha256(source.read_bytes()).hexdigest()
