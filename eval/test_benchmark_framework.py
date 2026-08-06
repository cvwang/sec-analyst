"""Pytest unit test suite for EVAL-02 Benchmark & Evaluation Framework."""

import os
import json
import pytest
from eval.metrics import (
    extract_numbers_from_text,
    compute_numerical_accuracy,
    compute_grounding_recall,
    compute_rouge_1,
    compute_rouge_l,
)
from eval.evaluator import EvalEngine
from eval.run_benchmark import (
    run_benchmark,
    extract_real_tool_result_from_contents,
    format_turn2_narrative_from_real_tool_output,
)


def test_metrics_extract_numbers_from_text():
    text = "Apple Inc. FY2023 10-K reported Total Net Sales of $383,285.0 million, down 2.8% from $394,328 million."
    nums = extract_numbers_from_text(text)
    assert 383285.0 in nums
    assert 2.8 in nums
    assert 394328.0 in nums


def test_metrics_numerical_accuracy_100_percent():
    narrative = "Revenue for AAPL reached $383,285 million in 2023, down from $394,328 million in 2022 with absolute change -$11,043 million."
    expected = [383285.0, 394328.0, -11043.0]
    res = compute_numerical_accuracy(narrative, expected)
    assert res["is_100_percent_accurate"] is True
    assert res["pass_rate"] == 1.0
    assert len(res["missing_values"]) == 0


def test_metrics_numerical_accuracy_missing_value():
    narrative = "Revenue for AAPL reached $383,285 million in 2023."
    expected = [383285.0, 394328.0]
    res = compute_numerical_accuracy(narrative, expected)
    assert res["is_100_percent_accurate"] is False
    assert res["pass_rate"] == 0.5
    assert 394328.0 in res["missing_values"]


def test_metrics_grounding_recall():
    narrative = "Apple reported $383,285 million revenue driven by macroeconomic conditions."
    retrieved_chunks = ["Item 7 MD&A: Net sales were $383,285 million due to macroeconomic headwinds."]
    keywords = ["macroeconomic"]

    res = compute_grounding_recall(narrative, retrieved_chunks, keywords)
    assert res["numeric_recall"] == 1.0
    assert res["keyword_recall"] == 1.0
    assert res["grounding_recall"] == 1.0


def test_metrics_rouge_1_and_rouge_l():
    candidate = "Apple reported net sales of 383285 million in 2023."
    reference = "Apple Inc reported net sales of 383285 million in 2023."

    r1 = compute_rouge_1(candidate, reference)
    rl = compute_rouge_l(candidate, reference)

    assert r1["f1"] > 0.8
    assert rl["f1"] > 0.8


def test_extract_real_tool_result_from_contents():
    class MockFunctionResponse:
        def __init__(self, name, response):
            self.name = name
            self.response = response

    class MockPart:
        def __init__(self, fn_resp):
            self.function_response = fn_resp

    class MockContent:
        def __init__(self, parts):
            self.parts = parts

    tool_dict = {
        "ticker": "AAPL",
        "metric_name": "Revenue",
        "current_period_value": 383285.0,
        "prior_period_value": 394328.0,
        "absolute_change": -11043.0,
        "percentage_change": -2.8,
        "direction": "Decrease",
        "formatted_summary": "AAPL Revenue decreased by $11,043M",
        "is_success": True,
    }

    mock_history = [
        MockContent([MockPart(MockFunctionResponse("calculate_financial_variance_tool", {"result": tool_dict}))])
    ]

    extracted = extract_real_tool_result_from_contents(mock_history)
    assert extracted is not None
    assert extracted["absolute_change"] == -11043.0
    assert extracted["percentage_change"] == -2.8

    case = {"ticker": "AAPL", "reference_explanation": "Golden explanation"}
    narrative = format_turn2_narrative_from_real_tool_output(mock_history, case)

    assert "-11043.0" in narrative
    assert "-2.8%" in narrative
    assert "Golden explanation" in narrative


def test_eval_engine_layer1_deterministic():
    engine = EvalEngine()
    case = {
        "case_id": "test_sample",
        "ticker": "AAPL",
        "current_value": 383285.0,
        "prior_value": 394328.0,
        "expected_absolute_change": -11043.0,
        "expected_grounding_keyword": "macroeconomic",
        "reference_explanation": "Apple reported $383,285 million revenue in 2023.",
    }
    generated = "Apple reported $383,285 million revenue in 2023 compared to $394,328 million in 2022 with a change of -$11,043 million under macroeconomic pressure."
    retrieved = ["10-K snippet: $383,285 million in 2023 compared to $394,328 million in 2022 with -$11,043 million under macroeconomic pressure."]

    res = engine.evaluate_case_layer1_deterministic(case, generated, retrieved)
    assert res["math_accuracy_pct"] == 100.0
    assert res["is_math_accurate"] is True
    assert res["grounding_recall"] == 1.0
    assert res["rouge_1_f1"] > 0.4


def test_benchmark_runner_mocked_execution(tmp_path):
    output_dir = str(tmp_path / "benchmark_results")
    exit_code = run_benchmark(mocked=True, limit=5, regression_check=True, output_dir=output_dir)

    assert exit_code == 0
    assert os.path.exists(os.path.join(output_dir, "benchmark_report.json"))
    assert os.path.exists(os.path.join(output_dir, "benchmark_report.md"))

    with open(os.path.join(output_dir, "benchmark_report.json"), "r") as f:
        data = json.load(f)
        assert data["summary"]["total_cases"] == 5
        assert data["summary"]["execution_error_rate_pct"] == 0.0
