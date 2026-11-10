from app.nodes.base import BaseNode
from app.schemas.workflow import NodeType
from app.workflow.exceptions import WorkflowValidationError


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[NodeType, type[BaseNode]] = {}

    def register(self, node_type: NodeType, node_class: type[BaseNode]) -> None:
        self._nodes[node_type] = node_class

    def create(self, node_type: NodeType) -> BaseNode:
        node_class = self._nodes.get(node_type)
        if node_class is None:
            raise WorkflowValidationError(f"No implementation registered for node type '{node_type}'")
        return node_class()

