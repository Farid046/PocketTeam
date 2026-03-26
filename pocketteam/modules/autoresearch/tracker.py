"""
Experiment Tracker — records experiments, results, and git state.

Stores experiments as JSONL for append-only tracking.
Each result is tied to a git commit for reproducibility.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExperimentResult:
    """A single experiment iteration result."""
    variation: str
    metric_value: float
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "variation": self.variation,
            "metric_value": self.metric_value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Experiment:
    """An experiment with its configuration and results."""
    name: str
    metric_name: str
    target_file: str
    maximize: bool = True
    max_iterations: int = 50
    results: list[ExperimentResult] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    @property
    def best_result(self) -> dict | None:
        """Get the best result based on maximize/minimize."""
        if not self.results:
            return None

        if self.maximize:
            best = max(self.results, key=lambda r: r.metric_value)
        else:
            best = min(self.results, key=lambda r: r.metric_value)

        return {
            "variation": best.variation,
            "metric_value": best.metric_value,
            "metric_name": self.metric_name,
        }

    @property
    def is_complete(self) -> bool:
        return len(self.results) >= self.max_iterations

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "metric_name": self.metric_name,
            "target_file": self.target_file,
            "maximize": self.maximize,
            "max_iterations": self.max_iterations,
            "created_at": self.created_at,
            "results": [r.to_dict() for r in self.results],
        }


class ExperimentTracker:
    """
    Tracks experiments and results on disk.

    Storage: .pocketteam/autoresearch/<experiment_name>.json
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._dir = project_root / ".pocketteam/autoresearch"
        self._experiments: dict[str, Experiment] = {}

    def create_experiment(
        self,
        name: str,
        metric_name: str,
        target_file: str,
        maximize: bool = True,
        max_iterations: int = 50,
    ) -> Experiment:
        """Create and persist a new experiment."""
        experiment = Experiment(
            name=name,
            metric_name=metric_name,
            target_file=target_file,
            maximize=maximize,
            max_iterations=max_iterations,
        )
        self._experiments[name] = experiment
        self._persist(experiment)
        return experiment

    def record_result(
        self,
        experiment_name: str,
        variation: str,
        metric_value: float,
        metadata: dict | None = None,
    ) -> bool:
        """
        Record a result. Returns True if experiment is still active.
        """
        experiment = self.get_experiment(experiment_name)
        if not experiment:
            return False

        if experiment.is_complete:
            return False

        result = ExperimentResult(
            variation=variation,
            metric_value=metric_value,
            metadata=metadata or {},
        )
        experiment.results.append(result)
        self._persist(experiment)

        # Also log to JSONL for append-only tracking
        self._append_log(experiment_name, result)

        return not experiment.is_complete

    def get_experiment(self, name: str) -> Experiment | None:
        """Get an experiment by name (from memory or disk)."""
        if name in self._experiments:
            return self._experiments[name]

        # Try loading from disk
        path = self._dir / f"{name}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                experiment = Experiment(
                    name=data["name"],
                    metric_name=data["metric_name"],
                    target_file=data["target_file"],
                    maximize=data.get("maximize", True),
                    max_iterations=data.get("max_iterations", 50),
                    created_at=data.get("created_at", ""),
                )
                for r in data.get("results", []):
                    experiment.results.append(ExperimentResult(
                        variation=r["variation"],
                        metric_value=r["metric_value"],
                        timestamp=r.get("timestamp", ""),
                        metadata=r.get("metadata", {}),
                    ))
                self._experiments[name] = experiment
                return experiment
            except Exception:
                return None

        return None

    def list_experiments(self) -> list[str]:
        """List all experiment names."""
        names = set(self._experiments.keys())

        if self._dir.exists():
            for f in self._dir.glob("*.json"):
                names.add(f.stem)

        return sorted(names)

    def _persist(self, experiment: Experiment) -> None:
        """Save experiment to disk."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._dir / f"{experiment.name}.json"
            path.write_text(json.dumps(experiment.to_dict(), indent=2))
        except Exception:
            pass

    def _append_log(self, experiment_name: str, result: ExperimentResult) -> None:
        """Append result to JSONL log."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            log_path = self._dir / f"{experiment_name}.jsonl"
            with open(log_path, "a") as f:
                entry = {
                    "experiment": experiment_name,
                    **result.to_dict(),
                }
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
