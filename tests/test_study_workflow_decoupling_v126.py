from pathlib import Path
import unittest

from research_platform.execution.workflow.implementations.context_action.context_action_workflow import ContextActionTrialProtocol
from research_platform.experimentation.experiment.runtime import ExperimentRuntime
from research_platform.experimentation.experiment.api import ExperimentTrialProtocol


class StudyWorkflowDecouplingV126Tests(unittest.TestCase):
    def test_default_workflow_is_a_replaceable_policy(self):
        self.assertIsInstance(ContextActionTrialProtocol(), ExperimentTrialProtocol)
        root = Path(__file__).resolve().parents[1]
        runtime_source = (root / "research_platform" / "experimentation" / "experiment" / "runtime" / "engine.py").read_text(encoding="utf-8")
        composition_source = (root / "research_platform" / "platform" / "composition" / "experiment_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("trial_protocol=", runtime_source)
        self.assertNotIn("participant_runtime", runtime_source)
        self.assertIn("trial_protocol", composition_source)
        self.assertIn("build_experiment_runtime", composition_source)
        self.assertNotIn("environment.observe\"", runtime_source)
        self.assertNotIn("method.recall\"", runtime_source)


if __name__ == "__main__":
    unittest.main()
