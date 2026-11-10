class WorkflowError(Exception):
    """Base exception for workflow validation and execution errors."""


class WorkflowValidationError(WorkflowError):
    pass


class NodeExecutionError(WorkflowError):
    def __init__(self, node_id: str, message: str):
        self.node_id = node_id
        super().__init__(f"Node '{node_id}' failed: {message}")

