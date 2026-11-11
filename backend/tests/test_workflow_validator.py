import pytest

from app.schemas.workflow import WorkflowDefinition
from app.workflow.exceptions import WorkflowValidationError
from app.workflow.validator import WorkflowValidator


def test_validator_returns_topological_order() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "simple",
            "nodes": [
                {"id": "input", "type": "input"},
                {"id": "agent", "type": "agent"},
                {"id": "output", "type": "output"},
            ],
            "edges": [
                {"source": "input", "target": "agent"},
                {"source": "agent", "target": "output"},
            ],
        }
    )

    assert WorkflowValidator.validate(workflow) == ["input", "agent", "output"]


def test_workflow_keeps_saved_node_position() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "positioned",
            "nodes": [
                {"id": "input", "type": "input", "position": {"x": 125, "y": 240}},
                {"id": "output", "type": "output", "position": {"x": 460.5, "y": 240}},
            ],
            "edges": [{"source": "input", "target": "output"}],
        }
    )

    assert workflow.model_dump(mode="json")["nodes"][0]["position"] == {"x": 125.0, "y": 240.0}


def test_validator_rejects_cycle() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "cycle",
            "nodes": [
                {"id": "input", "type": "input"},
                {"id": "output", "type": "output"},
            ],
            "edges": [
                {"source": "input", "target": "output"},
                {"source": "output", "target": "input"},
            ],
        }
    )

    with pytest.raises(WorkflowValidationError, match="cycle"):
        WorkflowValidator.validate(workflow)


def test_validator_rejects_edge_into_input() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "backwards",
            "nodes": [
                {"id": "input", "type": "input"},
                {"id": "agent", "type": "agent"},
                {"id": "output", "type": "output"},
            ],
            "edges": [
                {"source": "agent", "target": "input"},
                {"source": "agent", "target": "output"},
            ],
        }
    )

    with pytest.raises(WorkflowValidationError, match="Input node 'input' cannot have incoming"):
        WorkflowValidator.validate(workflow)


def test_validator_rejects_agent_without_upstream() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "orphan-agent",
            "nodes": [
                {"id": "input", "type": "input"},
                {"id": "agent", "type": "agent"},
                {"id": "output", "type": "output"},
            ],
            "edges": [
                {"source": "input", "target": "output"},
                {"source": "agent", "target": "output"},
            ],
        }
    )

    with pytest.raises(WorkflowValidationError, match="Node 'agent' requires an upstream"):
        WorkflowValidator.validate(workflow)

