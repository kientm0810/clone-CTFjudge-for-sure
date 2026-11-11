import pytest

from app.services.report_service import build_ctfjudge_report


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
