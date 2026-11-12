from app.nodes.base import BaseNode, NodeResult
from app.schemas.workflow import NodeDefinition
from app.workflow.context import WorkflowContext
from app.workflow.exceptions import NodeExecutionError
from app.services.report_service import build_ctfjudge_report, build_similarity_report


class OutputNode(BaseNode):
    async def execute(
        self,
        definition: NodeDefinition,
        inputs: dict,
        context: WorkflowContext,
    ) -> NodeResult:
        value = inputs if definition.inputs else (
            next(iter(inputs.values())) if len(inputs) == 1 else inputs
        )
        output_format = definition.config.get("format")
        if output_format in {"ctfjudge_report", "comparison_report"}:
            try:
                report_value = inputs.get("analysis")
                retrieval_results = inputs.get("retrieval_results")
                golden_chunks = inputs.get("golden_chunks")
                if report_value is None:
                    report_value = value
                if not definition.inputs and len(inputs) > 1:
                    report_value = next(
                        (item for item in inputs.values() if isinstance(item, dict) and "comparisons" in item),
                        None,
                    )
                    retrieval_source = next(
                        (item for item in inputs.values() if isinstance(item, dict) and "retrieval_results" in item),
                        None,
                    )
                    retrieval_results = retrieval_source.get("retrieval_results") if retrieval_source else None
                    chunks_source = next(
                        (
                            item for item in inputs.values()
                            if isinstance(item, dict)
                            and isinstance(item.get("chunks"), list)
                            and any(
                                str(chunk.get("chunk_id", "")).startswith("golden-")
                                for chunk in item["chunks"]
                                if isinstance(chunk, dict)
                            )
                        ),
                        None,
                    )
                    golden_chunks = chunks_source.get("chunks") if chunks_source else None
                if output_format == "ctfjudge_report":
                    value = build_ctfjudge_report(
                        report_value,
                        definition.config.get("formula_weights"),
                        retrieval_results=retrieval_results,
                    )
                else:
                    value = build_similarity_report(
                        report_value,
                        retrieval_results=retrieval_results,
                        golden_chunks=golden_chunks,
                    )
            except ValueError as exc:
                raise NodeExecutionError(definition.id, str(exc)) from exc
        return NodeResult(value=value)

