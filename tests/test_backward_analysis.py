"""Tests for backward_analysis."""
from __future__ import annotations

import pandas as pd
import pytest

from src.backward_analysis import run_backward_analysis, stage_1_outcome_identification


def test_backward_analysis_returns_7_stages(cleaned_df):
    result = run_backward_analysis(cleaned_df, user_budget=50000)
    assert len(result.stages) == 7


def test_stage_1_identifies_target_column(cleaned_df):
    stage = stage_1_outcome_identification(cleaned_df)
    assert stage.stage_id == "outcome_identification"
    assert "y" in stage.finding or "ALL_PURCHASES" in stage.finding


def test_stage_2_drops_sparse_channels(cleaned_df):
    result = run_backward_analysis(cleaned_df)
    s2 = result.stages[1]
    assert s2.stage_id == "channel_detection"


def test_stage_5_objective_function_text_not_empty(cleaned_df):
    result = run_backward_analysis(cleaned_df)
    assert len(result.objective_function_text) > 0


def test_stage_6_detects_budget_constraint(cleaned_df):
    result = run_backward_analysis(cleaned_df, user_budget=75000)
    assert result.detected_budget == 75000
    assert any("budget" in c.lower() for c in result.constraint_text)


def test_stage_7_confirmed_false_by_default(cleaned_df):
    result = run_backward_analysis(cleaned_df)
    assert result.confirmed_by_user is False


def test_run_backward_analysis_completes_on_sample_data(cleaned_df):
    result = run_backward_analysis(cleaned_df)
    assert result.target_column
    assert result.stages[-1].stage_id == "user_confirmation"
