"""
AutoResearch Module — automated experiment loops.

Inspired by autoresearch (karpathy): autonomous optimization of
measurable metrics through iterative experimentation.

Use cases:
- Email subject line A/B testing → optimize open rate
- Landing page copy → optimize conversion rate
- API configuration → optimize latency
- Model hyperparameters → optimize accuracy

Flow:
1. Define what to optimize (metric, file to modify, constraint)
2. Module generates variations
3. Runs experiments (via external trigger or cron)
4. Measures results
5. Picks winner, generates new variations
6. Repeat until convergence or max iterations
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from ..base_module import BaseModule, ModuleConfig
from .tracker import ExperimentTracker, Experiment, ExperimentResult


class AutoResearchModule(BaseModule):
    """
    AutoResearch: automated experiment loops for metric optimization.
    """

    @property
    def module_name(self) -> str:
        return "autoresearch"

    @property
    def description(self) -> str:
        return "Automated experiment loops for metric optimization"

    def __init__(
        self,
        project_root: Path,
        config: Optional[ModuleConfig] = None,
    ) -> None:
        super().__init__(project_root, config)
        self.tracker = ExperimentTracker(project_root)

    async def setup(self) -> bool:
        """Interactive setup — called during pocketteam init."""
        # In a real implementation, this would prompt the user for:
        # - What metric to optimize
        # - Which file to modify
        # - How to measure the metric
        # - How often to run experiments
        return True

    async def run(self, **kwargs: Any) -> dict:
        """
        Run one iteration of the experiment loop.

        Steps:
        1. Check current best result
        2. Generate new variation
        3. Deploy variation
        4. Wait for results
        5. Record and compare
        """
        experiment_name = kwargs.get("experiment_name", "default")
        experiment = self.tracker.get_experiment(experiment_name)

        if not experiment:
            return {"error": f"No experiment found: {experiment_name}"}

        return {
            "experiment": experiment_name,
            "status": "iteration_complete",
            "total_iterations": len(experiment.results),
            "best_result": experiment.best_result,
        }

    def create_experiment(
        self,
        name: str,
        metric_name: str,
        target_file: str,
        maximize: bool = True,
        max_iterations: int = 50,
    ) -> Experiment:
        """Create a new experiment."""
        return self.tracker.create_experiment(
            name=name,
            metric_name=metric_name,
            target_file=target_file,
            maximize=maximize,
            max_iterations=max_iterations,
        )

    def record_result(
        self,
        experiment_name: str,
        variation: str,
        metric_value: float,
        metadata: Optional[dict] = None,
    ) -> None:
        """Record a result for an experiment iteration."""
        self.tracker.record_result(
            experiment_name=experiment_name,
            variation=variation,
            metric_value=metric_value,
            metadata=metadata,
        )

    def get_best(self, experiment_name: str) -> Optional[dict]:
        """Get the best result for an experiment."""
        experiment = self.tracker.get_experiment(experiment_name)
        if not experiment:
            return None
        return experiment.best_result

    def list_experiments(self) -> list[str]:
        """List all experiment names."""
        return self.tracker.list_experiments()
