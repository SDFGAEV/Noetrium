import unittest


class PublicAPIImportTests(unittest.TestCase):
    def test_core_public_packages_import(self):
        import noetrium_platform.evidence.observability.telemetry as telemetry
        import noetrium_platform.infrastructure.reliability.forensics as forensics
        import noetrium_platform.capabilities.model.serving as model_serving
        import noetrium_platform.product.operator as operator
        import noetrium_platform.capabilities.model.request.prompt.runtime as prompt_runtime
        for module in (telemetry, forensics, model_serving, operator, prompt_runtime):
            self.assertIsNotNone(module)

    def test_public_contract_and_extension_layers_are_discoverable(self):
        import components
        import noetrium
        import noetrium.adapters
        import noetrium.contracts
        import orchestration
        from noetrium.contracts import AgentGoal, JsonValue, ResearchMethodHost
        from orchestration.multi_agent import MultiAgentCoordinator

        self.assertEqual(noetrium.__all__, ["__version__"])
        self.assertIsNotNone(AgentGoal)
        self.assertIsNotNone(JsonValue)
        self.assertIsNotNone(ResearchMethodHost)
        self.assertIsNotNone(components.reference)
        self.assertIsNotNone(MultiAgentCoordinator)


if __name__ == '__main__':
    unittest.main()
