from collections import defaultdict, deque

from app.schemas.workflow import NodeType, WorkflowDefinition
from app.workflow.exceptions import WorkflowValidationError
from app.workflow.expressions import iter_expressions, referenced_step


class WorkflowValidator:
    @staticmethod
    def validate(workflow: WorkflowDefinition) -> list[str]:
        node_by_id = {node.id: node for node in workflow.nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)
        indegree = {node.id: 0 for node in workflow.nodes}

        for edge in workflow.edges:
            if edge.source not in node_by_id:
                raise WorkflowValidationError(f"Edge source '{edge.source}' does not exist")
            if edge.target not in node_by_id:
                raise WorkflowValidationError(f"Edge target '{edge.target}' does not exist")
            if edge.source == edge.target:
                raise WorkflowValidationError(f"Node '{edge.source}' cannot connect to itself")
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1

        input_nodes = [node for node in workflow.nodes if node.type == NodeType.INPUT]
        output_nodes = [node for node in workflow.nodes if node.type == NodeType.OUTPUT]
        if not input_nodes:
            raise WorkflowValidationError("Workflow must contain at least one input node")
        if not output_nodes:
            raise WorkflowValidationError("Workflow must contain at least one output node")

        queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
        ordered: list[str] = []
        while queue:
            node_id = queue.popleft()
            ordered.append(node_id)
            for target in adjacency[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)

        if len(ordered) != len(workflow.nodes):
            raise WorkflowValidationError("Workflow contains a cycle")

        incoming_count = {node.id: 0 for node in workflow.nodes}
        outgoing_count = {node.id: 0 for node in workflow.nodes}
        for edge in workflow.edges:
            incoming_count[edge.target] += 1
            outgoing_count[edge.source] += 1

        invalid_input = next((node.id for node in input_nodes if incoming_count[node.id] > 0), None)
        if invalid_input:
            raise WorkflowValidationError(f"Input node '{invalid_input}' cannot have incoming edges")

        invalid_output = next((node.id for node in output_nodes if outgoing_count[node.id] > 0), None)
        if invalid_output:
            raise WorkflowValidationError(f"Output node '{invalid_output}' cannot have outgoing edges")

        missing_upstream = next(
            (node.id for node in workflow.nodes if node.type != NodeType.INPUT and incoming_count[node.id] == 0),
            None,
        )
        if missing_upstream:
            raise WorkflowValidationError(f"Node '{missing_upstream}' requires an upstream connection")

        missing_downstream = next(
            (node.id for node in workflow.nodes if node.type != NodeType.OUTPUT and outgoing_count[node.id] == 0),
            None,
        )
        if missing_downstream:
            raise WorkflowValidationError(f"Node '{missing_downstream}' requires a downstream connection")

        connected = {edge.source for edge in workflow.edges} | {edge.target for edge in workflow.edges}
        isolated = [node.id for node in workflow.nodes if node.id not in connected and len(workflow.nodes) > 1]
        if isolated:
            raise WorkflowValidationError(f"Workflow contains isolated nodes: {', '.join(isolated)}")

        ancestors: dict[str, set[str]] = {node.id: set() for node in workflow.nodes}
        for node_id in ordered:
            for target in adjacency[node_id]:
                ancestors[target].add(node_id)
                ancestors[target].update(ancestors[node_id])

        for node in workflow.nodes:
            for expression in iter_expressions(node.inputs):
                step_id = referenced_step(expression)
                if step_id is not None:
                    if step_id not in node_by_id:
                        raise WorkflowValidationError(
                            f"Node '{node.id}' references missing step '{step_id}'"
                        )
                    if step_id not in ancestors[node.id]:
                        raise WorkflowValidationError(
                            f"Node '{node.id}' can only reference connected upstream steps; "
                            f"'{step_id}' is not upstream"
                        )
                elif not (
                    expression.startswith("runtime.")
                    or expression in {"run.id", "run_id"}
                ):
                    raise WorkflowValidationError(
                        f"Node '{node.id}' contains unsupported expression '{{{{ {expression} }}}}'"
                    )

        return ordered

