import numpy as np

from app.condition import RuleConditionClassifier
from app.runtime.online_condition_encoder import OnlineConditionEncoder
from app.condition import ConditionFeatureExtractor


MAPPING = {
    0: "高速巡航",
    1: "进站减速",
    2: "出站加速",
}


def test_rule_condition_classifier_outputs_three_fixed_conditions():
    classifier = RuleConditionClassifier(condition_label_mapping=MAPPING)
    feature_columns = ["速度", "制动信息"]

    accel_window = np.column_stack(
        [np.linspace(30, 125, 30), np.zeros(30)]
    ).astype(np.float32)
    cruise_window = np.column_stack(
        [np.full(30, 245.0) + np.sin(np.arange(30)) * 2.0, np.zeros(30)]
    ).astype(np.float32)
    decel_window = np.column_stack(
        [np.linspace(250, 90, 30), np.ones(30)]
    ).astype(np.float32)

    assert classifier.classify(accel_window, feature_columns).condition_label == "出站加速"
    assert classifier.classify(cruise_window, feature_columns).condition_label == "高速巡航"
    assert classifier.classify(decel_window, feature_columns).condition_label == "进站减速"


class _DummyKMeans:
    def predict(self, values):
        return np.zeros(values.shape[0], dtype=np.int64)


def test_online_condition_encoder_uses_raw_window_rule_anchor_trace(tmp_path):
    encoder = OnlineConditionEncoder(
        condition_model_path=tmp_path / "condition_model.pkl",
        condition_summary_path=None,
        model_info={"kmeans": _DummyKMeans(), "condition_label_mapping": MAPPING},
        summary={},
        n_clusters=3,
        condition_label_mapping=MAPPING,
        extractor=ConditionFeatureExtractor(),
    )
    raw_window = np.column_stack(
        [np.linspace(30, 125, 30), np.zeros(30)]
    ).astype(np.float32)
    scaled_window = raw_window.copy()

    result = encoder.encode(
        scaled_window,
        base_feature_columns=["速度", "制动信息"],
        condition_columns=["condition_0", "condition_1", "condition_2"],
        raw_base_window=raw_window,
    )

    assert result["condition_label"] == "出站加速"
    assert result["condition_id"] == 2
    assert result["condition_one_hot"].tolist() == [0.0, 0.0, 1.0]
    assert result["trace"]["kmeans_condition_label"] == "高速巡航"
    assert result["trace"]["rule_condition_label"] == "出站加速"
    assert result["trace"]["final_condition_source"] == "rule_anchor"
