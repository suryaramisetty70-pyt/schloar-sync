"""Exercise the actual CrewAI router without making paid model calls."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch


class SpecialistTests(unittest.TestCase):
    def test_router_and_crew(self):
        from crewai import Agent, Crew
        from crewai.flow import Flow
        from crewai.flow.expressions import Expression
        from crewai.lite_agent_output import LiteAgentOutput
        from multi_agent_ai_system.worker import hosted_definition

        path = Path(__file__).resolve().parents[1] / "src/multi_agent_ai_system/flow.json"
        definition = hosted_definition()
        route = definition["methods"]["route_message"]
        expression = Expression("${" + route["do"]["expr"] + "}")
        for label in route["emit"]:
            category = "quick" if label == "quick_answer" else label
            verdict = "BLOCK" if label == "blocked" else "PASS"
            raw = f"LANGUAGE: English\nVERDICT: {verdict}\nCATEGORY: {category}\nCLEAN REQUEST: sample\nBLOCK MESSAGE: none"
            with self.subTest(label=label):
                self.assertEqual(expression.evaluate({"outputs": {"planner": {"raw": raw}}}), label)

        async def agent(self, *args, **kwargs):
            return LiteAgentOutput(raw="LANGUAGE: English\nVERDICT: PASS\nCATEGORY: math\nCLEAN REQUEST: Explain fractions\nBLOCK MESSAGE: none", agent_role=self.role)

        async def crew(self, inputs=None, **kwargs):
            assert inputs["message"] == "Explain fractions"
            return LiteAgentOutput(raw="Simulated test result", agent_role="Math team")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-fixture-only", "CREWAI_TRACING_ENABLED": "false", "OTEL_SDK_DISABLED": "true"}), patch.object(Agent, "kickoff_async", agent), patch.object(Crew, "kickoff_async", crew):
            result = Flow.from_declaration(contents=definition).kickoff(inputs={"message": "Explain fractions", "user_id": "test-user"})
        self.assertEqual(result.raw, "Simulated test result")
