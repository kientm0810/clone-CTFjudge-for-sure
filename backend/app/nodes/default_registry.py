from app.nodes.agent_node import AgentNode
from app.nodes.database_node import DatabaseNode
from app.nodes.input_node import InputNode
from app.nodes.output_node import OutputNode
from app.nodes.registry import NodeRegistry
from app.schemas.workflow import NodeType


def build_default_registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(NodeType.INPUT, InputNode)
    registry.register(NodeType.AGENT, AgentNode)
    registry.register(NodeType.DATABASE, DatabaseNode)
    registry.register(NodeType.OUTPUT, OutputNode)
    return registry

