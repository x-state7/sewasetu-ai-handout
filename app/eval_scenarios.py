
"""Persona-based, read-only MCP evaluation scenarios.

Tokens and application references come from the deployment environment.
Never hardcode real citizen data or credentials into this module.
"""

from dataclasses import dataclass, field
from typing import Any
import os


@dataclass(frozen=True)
class Scenario:
    id: str
    persona: str
    prompt: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    expectation: str = "success"
    expected_status: str | None = None


def build_scenarios():
    cases = [
        Scenario(
            id="C01",
            persona="citizen_a",
            prompt="I've applied for the pension scheme. "
                   "Can you show me my applications?",
            tool="list_my_applications",
            expectation="application_list",
        ),
        Scenario(
            id="C02",
            persona="citizen_b",
            prompt="I don't remember my application number. "
                   "Show me my submitted applications.",
            tool="list_my_applications",
            expectation="application_list",
        ),
        Scenario(
            id="O01",
            persona="officer",
            prompt="How many applications are pending, approved, "
                   "rejected or withdrawn?",
            tool="application_status_counts",
            expectation="status_counts",
        ),
        Scenario(
            id="O02",
            persona="officer",
            prompt="Show me the oldest pending cases that need review.",
            tool="pending_application_queue",
            arguments={"limit": 10},
            expectation="pending_queue",
        ),
    ]

    owned = os.getenv("EVAL_CITIZEN_A_APPLICATION_NO", "").strip()
    if owned:
        cases.append(Scenario(
            id="C03",
            persona="citizen_a",
            prompt="What is the status of my application?",
            tool="get_my_application_status",
            arguments={"application_no": owned},
            expectation="found",
            expected_status=os.getenv(
                "EVAL_CITIZEN_A_EXPECTED_STATUS"
            ) or None,
        ))

        cases.append(Scenario(
            id="C04",
            persona="citizen_b",
            prompt="Can I see the status of this other "
                   "person's application?",
            tool="get_my_application_status",
            arguments={"application_no": owned},
            expectation="not_found",
        ))

        cases.append(Scenario(
            id="O03",
            persona="officer",
            prompt="Look up this application and tell me "
                   "its current processing status.",
            tool="application_status",
            arguments={"application_no": owned},
            expectation="found",
        ))

    return cases
