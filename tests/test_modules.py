"""
Tests for Phase 14: AutoResearch Module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pocketteam.modules.base_module import BaseModule, ModuleConfig
from pocketteam.modules.autoresearch.module import AutoResearchModule
from pocketteam.modules.autoresearch.tracker import (
    Experiment,
    ExperimentResult,
    ExperimentTracker,
)


# ── BaseModule ──────────────────────────────────────────────────────────────

class TestBaseModule:
    def test_module_config_defaults(self):
        cfg = ModuleConfig(name="test")
        assert cfg.enabled is True
        assert cfg.settings == {}

    def test_module_config_custom(self):
        cfg = ModuleConfig(name="test", enabled=False, settings={"key": "val"})
        assert cfg.enabled is False
        assert cfg.settings["key"] == "val"


# ── ExperimentResult ────────────────────────────────────────────────────────

class TestExperimentResult:
    def test_to_dict(self):
        r = ExperimentResult(
            variation="Subject A",
            metric_value=0.42,
            metadata={"sample_size": 100},
        )
        d = r.to_dict()
        assert d["variation"] == "Subject A"
        assert d["metric_value"] == 0.42
        assert d["metadata"]["sample_size"] == 100
        assert "timestamp" in d


# ── Experiment ──────────────────────────────────────────────────────────────

class TestExperiment:
    def test_best_result_maximize(self):
        exp = Experiment(
            name="email-open-rate",
            metric_name="open_rate",
            target_file="subjects.yaml",
            maximize=True,
        )
        exp.results = [
            ExperimentResult(variation="A", metric_value=0.20),
            ExperimentResult(variation="B", metric_value=0.35),
            ExperimentResult(variation="C", metric_value=0.28),
        ]
        best = exp.best_result
        assert best["variation"] == "B"
        assert best["metric_value"] == 0.35

    def test_best_result_minimize(self):
        exp = Experiment(
            name="latency",
            metric_name="p99_ms",
            target_file="config.yaml",
            maximize=False,
        )
        exp.results = [
            ExperimentResult(variation="config-1", metric_value=150),
            ExperimentResult(variation="config-2", metric_value=85),
            ExperimentResult(variation="config-3", metric_value=120),
        ]
        best = exp.best_result
        assert best["variation"] == "config-2"
        assert best["metric_value"] == 85

    def test_best_result_empty(self):
        exp = Experiment(
            name="empty",
            metric_name="x",
            target_file="y",
        )
        assert exp.best_result is None

    def test_is_complete(self):
        exp = Experiment(
            name="test",
            metric_name="x",
            target_file="y",
            max_iterations=3,
        )
        assert exp.is_complete is False
        exp.results = [ExperimentResult(variation=f"v{i}", metric_value=i) for i in range(3)]
        assert exp.is_complete is True

    def test_to_dict(self):
        exp = Experiment(
            name="test",
            metric_name="accuracy",
            target_file="model.py",
        )
        d = exp.to_dict()
        assert d["name"] == "test"
        assert d["metric_name"] == "accuracy"
        assert d["results"] == []


# ── ExperimentTracker ───────────────────────────────────────────────────────

class TestExperimentTracker:
    def test_create_experiment(self, tmp_path: Path):
        tracker = ExperimentTracker(tmp_path)
        exp = tracker.create_experiment(
            name="email-test",
            metric_name="open_rate",
            target_file="subjects.yaml",
        )
        assert exp.name == "email-test"
        # Should persist to disk
        assert (tmp_path / ".pocketteam/autoresearch/email-test.json").exists()

    def test_record_result(self, tmp_path: Path):
        tracker = ExperimentTracker(tmp_path)
        tracker.create_experiment(
            name="exp1",
            metric_name="ctr",
            target_file="copy.txt",
        )
        active = tracker.record_result("exp1", "variation-a", 0.05)
        assert active is True

        exp = tracker.get_experiment("exp1")
        assert len(exp.results) == 1
        assert exp.results[0].metric_value == 0.05

    def test_record_result_nonexistent(self, tmp_path: Path):
        tracker = ExperimentTracker(tmp_path)
        result = tracker.record_result("nope", "v1", 0.1)
        assert result is False

    def test_record_result_complete(self, tmp_path: Path):
        tracker = ExperimentTracker(tmp_path)
        tracker.create_experiment(
            name="short",
            metric_name="x",
            target_file="y",
            max_iterations=2,
        )
        tracker.record_result("short", "v1", 1.0)
        tracker.record_result("short", "v2", 2.0)
        # Experiment is now complete
        active = tracker.record_result("short", "v3", 3.0)
        assert active is False

    def test_list_experiments(self, tmp_path: Path):
        tracker = ExperimentTracker(tmp_path)
        tracker.create_experiment("exp-a", "m1", "f1")
        tracker.create_experiment("exp-b", "m2", "f2")
        names = tracker.list_experiments()
        assert "exp-a" in names
        assert "exp-b" in names

    def test_list_experiments_empty(self, tmp_path: Path):
        tracker = ExperimentTracker(tmp_path)
        assert tracker.list_experiments() == []

    def test_load_from_disk(self, tmp_path: Path):
        # Create with one tracker
        t1 = ExperimentTracker(tmp_path)
        t1.create_experiment("persistent", "metric", "file.txt")
        t1.record_result("persistent", "v1", 42.0)

        # Load with a fresh tracker
        t2 = ExperimentTracker(tmp_path)
        exp = t2.get_experiment("persistent")
        assert exp is not None
        assert len(exp.results) == 1
        assert exp.results[0].metric_value == 42.0

    def test_jsonl_log_created(self, tmp_path: Path):
        tracker = ExperimentTracker(tmp_path)
        tracker.create_experiment("logged", "x", "y")
        tracker.record_result("logged", "v1", 1.0)
        tracker.record_result("logged", "v2", 2.0)

        log_path = tmp_path / ".pocketteam/autoresearch/logged.jsonl"
        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2


# ── AutoResearchModule ──────────────────────────────────────────────────────

class TestAutoResearchModule:
    def test_module_name(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        assert mod.module_name == "autoresearch"
        assert mod.description != ""

    async def test_setup(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        result = await mod.setup()
        assert result is True

    def test_create_experiment(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        exp = mod.create_experiment(
            name="test-exp",
            metric_name="conversion_rate",
            target_file="landing.html",
        )
        assert exp.name == "test-exp"

    def test_record_and_get_best(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        mod.create_experiment(
            name="best-test",
            metric_name="score",
            target_file="config.yaml",
        )
        mod.record_result("best-test", "option-a", 10.0)
        mod.record_result("best-test", "option-b", 25.0)
        mod.record_result("best-test", "option-c", 15.0)

        best = mod.get_best("best-test")
        assert best is not None
        assert best["variation"] == "option-b"

    def test_get_best_nonexistent(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        assert mod.get_best("nope") is None

    def test_list_experiments(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        mod.create_experiment("a", "m", "f")
        mod.create_experiment("b", "m", "f")
        names = mod.list_experiments()
        assert len(names) == 2

    async def test_run_with_experiment(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        mod.create_experiment("runner-test", "metric", "file")
        mod.record_result("runner-test", "v1", 5.0)

        result = await mod.run(experiment_name="runner-test")
        assert result["experiment"] == "runner-test"
        assert result["total_iterations"] == 1

    async def test_run_nonexistent_experiment(self, tmp_path: Path):
        mod = AutoResearchModule(tmp_path)
        result = await mod.run(experiment_name="ghost")
        assert "error" in result
