import pytest

from app.services.report_service import build_ctfjudge_report, build_similarity_report


def test_build_ctfjudge_report_calculates_weighted_score() -> None:
    report = build_ctfjudge_report(
        {
            "summary": "Strong solution",
            "competency_matrix": {
                "vulnerability_understanding": "Deep",
                "reconnaissance_thoroughness": "Adequate",
                "exploitation_methodology": "Competent",
                "technical_accuracy": "Precise",
                "efficiency_approach": "Efficient",
                "adaptability": "Fair",
            },
        }
    )

    assert report["overall_score"] == 0.795
    assert report["formula_breakdown"]["technical_accuracy"] == {
        "rating": "Precise",
        "score": 1.0,
        "weight": 0.17,
        "weighted_score": 0.17,
    }


def test_build_ctfjudge_report_rejects_unknown_rating() -> None:
    with pytest.raises(ValueError, match="Unsupported rating"):
        build_ctfjudge_report(
            {
                "competency_matrix": {
                    "vulnerability_understanding": "Amazing",
                    "reconnaissance_thoroughness": "Adequate",
                    "exploitation_methodology": "Competent",
                    "technical_accuracy": "Precise",
                    "efficiency_approach": "Efficient",
                    "adaptability": "Fair",
                }
            }
        )


def test_report_grounds_each_student_chunk_and_normalizes_ai_score() -> None:
    matrix = {
        "vulnerability_understanding": "Deep",
        "reconnaissance_thoroughness": "Adequate",
        "exploitation_methodology": "Competent",
        "technical_accuracy": "Precise",
        "efficiency_approach": "Efficient",
        "adaptability": "Fair",
    }
    report = build_ctfjudge_report(
        {
            "competency_matrix": matrix,
            "comparisons": [{
                "student_chunk_id": "student-0",
                "student_content": "hallucinated",
                "classification": "partial_match",
                "score": 5,
                "explanation": "Đúng một phần.",
            }],
        },
        retrieval_results=[{
            "student_chunk_id": "student-0",
            "student_content": "Nội dung thật của sinh viên.",
            "candidates": [{
                "golden_chunk_id": "golden-2",
                "content": "Golden evidence",
                "similarity_score": 0.88,
            }],
        }],
    )

    comparison = report["comparisons"][0]
    assert comparison["student_content"] == "Nội dung thật của sinh viên."
    assert comparison["score"] == 0.5
    assert comparison["matched_golden"] == [{
        "chunk_id": "golden-2",
        "content": "Golden evidence",
        "similarity_score": 0.88,
    }]


def test_similarity_report_has_no_ctfjudge_rubric() -> None:
    report = build_similarity_report(
        {
            "summary": "Hai đoạn tương đồng.",
            "competency_matrix": {"technical_accuracy": "Good"},
            "comparisons": [
                {"student_chunk_id": "student-0", "score": 0.8},
                {"student_chunk_id": "student-1", "score": 0.4},
            ],
        },
        golden_chunks=[{"chunk_id": "golden-0", "content": "Expected evidence"}],
    )

    assert report["report_type"] == "similarity"
    assert report["summary_score"] == 0.6
    assert report["golden_chunks"][0]["chunk_id"] == "golden-0"
    assert "competency_matrix" not in report
    assert "overall_score" not in report


@pytest.mark.parametrize(
    ("defect_count", "material_count", "expected_label", "expected_score"),
    [
        (0, 0, "excellent", 0.92),
        (2, 0, "good", 0.78),
        (5, 1, "average", 0.60),
        (7, 0, "weak", 0.35),
        (3, 2, "weak", 0.35),
    ],
)
def test_similarity_report_derives_label_from_structured_defects(
    defect_count: int,
    material_count: int,
    expected_label: str,
    expected_score: float,
) -> None:
    report = build_similarity_report(
        {
            "summary": "Structured audit",
            "comparisons": [],
            "overall_score": 0.99,
            "quality_label": "excellent",
            "defects": [f"defect-{index}" for index in range(defect_count)],
            "defect_count": defect_count,
            "material_defect_count": material_count,
        }
    )

    assert report["quality_label"] == expected_label
    assert report["summary_score"] == expected_score
    assert report["defect_count"] == defect_count
