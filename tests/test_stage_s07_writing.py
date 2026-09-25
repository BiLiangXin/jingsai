"""Public-source checks for S07 writing claims; no private data or model execution."""
from pathlib import Path
import ast
import csv
import importlib.util
from collections import defaultdict
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]


def test_autoqc_edit_distance_denominator_matches_written_correction():
    path = ROOT / "src/mosei/autoqc/core.py"
    source = path.read_text(encoding="utf-8")
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "unique_exact_matches")
    body = ast.get_source_segment(source, function)
    assert "cost[-1][-1] / len(ref)" in body
    assert "if not ref" in body
    spec = importlib.util.spec_from_file_location("s07_bound_autoqc_core", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    insertion = module.unique_exact_matches(["a", "b"], ["a", "b", "c"])
    assert insertion["edit_distance"] == 1
    assert insertion["disagreement"] == 0.5  # wrong max-length denominator gives 1/3
    empty = module.unique_exact_matches([], ["c"])
    assert empty["disagreement"] is None and empty["reason"] == "EMPTY_REFERENCE"


def test_factor_table_contains_three_seed_rows_per_group():
    path = ROOT / "reports/s02_execution/S02-20260925-BOUNDED-12F15W/FACTOR_DESCRIPTIVES.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    groups = defaultdict(list)
    for row in rows:
        groups[(row["configuration"], row["dimension"], row["value"])].append(row)
    assert len(rows) == 798
    assert len(groups) == 266
    for group in groups.values():
        assert {row["seed"] for row in group} == {"17", "29", "43"}
        assert abs(mean(float(row["macro_F1"]) for row in group)
                   - float(group[0]["macro_F1_mean"])) < 1e-12
