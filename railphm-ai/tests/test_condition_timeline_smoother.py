from app.condition.condition_timeline_smoother import ConditionTimelineSmoother


def _build_results(labels):
    return [
        {
            "time": f"2026-05-18 09:00:{index:02d}",
            "condition_label": label,
            "risk_raw": 0.3 + index / 100,
            "risk_score": 0.2 + index / 100,
            "risk_raw_std": 0.01,
            "risk_std": 0.02,
            "threshold": 0.58,
            "predicted_label": int(index % 2 == 0),
            "model_name": "test-model",
            "model_version": "test-version",
            "trace": {"original": index},
        }
        for index, label in enumerate(labels)
    ]


def _smooth_labels(labels):
    smoother = ConditionTimelineSmoother(min_confirm_points=5, min_segment_points=5)
    return smoother.smooth(_build_results(labels))


def test_smoother_absorbs_short_deceleration_inside_cruise():
    labels = ["高速巡航", "高速巡航", "进站减速", "高速巡航", "高速巡航"]

    results = _smooth_labels(labels)

    assert [item["condition_label"] for item in results] == ["高速巡航"] * 5
    assert results[2]["trace"]["raw_condition_label_before_smooth"] == "进站减速"
    assert results[2]["trace"]["smoothed_condition_label"] == "高速巡航"
    assert results[2]["trace"]["condition_smooth_applied"] is True
    assert results[2]["trace"]["condition_smooth_reason"] == "cruise_sandwich_guard"
    assert results[2]["risk_score"] == 0.22


def test_smoother_keeps_confirmed_deceleration_transition():
    labels = [
        "高速巡航",
        "高速巡航",
        "进站减速",
        "进站减速",
        "进站减速",
        "进站减速",
        "进站减速",
        "进站减速",
    ]

    results = _smooth_labels(labels)

    assert [item["condition_label"] for item in results[:2]] == ["高速巡航", "高速巡航"]
    assert [item["condition_label"] for item in results[2:]] == ["进站减速"] * 6
    assert results[2]["trace"]["condition_smooth_applied"] is False
    assert results[2]["trace"]["condition_smooth_reason"] == "confirmed_transition"


def test_smoother_preserves_complete_main_phases():
    labels = ["出站加速"] * 5 + ["高速巡航"] * 6 + ["进站减速"] * 5

    results = _smooth_labels(labels)

    assert [item["condition_label"] for item in results] == labels
    assert results[0]["trace"]["condition_smooth_reason"] == "unchanged"
    assert results[5]["trace"]["condition_smooth_reason"] == "confirmed_transition"
    assert results[11]["trace"]["condition_smooth_reason"] == "confirmed_transition"


def test_smoother_preserves_short_boundary_segments_and_missing_labels():
    labels = ["出站加速", "出站加速", None, "高速巡航", "进站减速", "进站减速"]

    results = _smooth_labels(labels)

    assert [item["condition_label"] for item in results] == labels
    assert results[0]["trace"]["condition_smooth_applied"] is False
    assert results[2]["trace"]["raw_condition_label_before_smooth"] is None
    assert results[-1]["trace"]["condition_smooth_reason"] in {
        "unchanged",
        "terminal_segment_preserved",
    }
