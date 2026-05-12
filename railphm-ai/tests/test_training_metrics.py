import numpy as np
import pytest

from app.training.metrics import compute_binary_metrics


def test_compute_binary_metrics_perfect_prediction():
    y_true = [0, 0, 1, 1]
    y_prob = [0.1, 0.2, 0.8, 0.9]

    metrics = compute_binary_metrics(y_true, y_prob)

    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["auc"] == 1.0
    assert metrics["brier_score"] == pytest.approx(
        np.mean((np.array(y_prob) - np.array(y_true)) ** 2)
    )
    assert metrics["confusion_matrix"] == {"tn": 2, "fp": 0, "fn": 0, "tp": 2}
    assert metrics["positive_count"] == 2
    assert metrics["negative_count"] == 2
    assert metrics["predicted_positive_count"] == 2
    assert metrics["predicted_negative_count"] == 2
    assert metrics["warnings"] == []


def test_compute_binary_metrics_all_wrong_prediction():
    y_true = [0, 0, 1, 1]
    y_prob = [0.9, 0.8, 0.2, 0.1]

    metrics = compute_binary_metrics(y_true, y_prob)

    assert metrics["accuracy"] == 0.0
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0
    assert metrics["auc"] == 0.0
    assert metrics["confusion_matrix"] == {"tn": 0, "fp": 2, "fn": 2, "tp": 0}


def test_threshold_effect():
    y_true = [0, 1, 1]
    y_prob = [0.4, 0.6, 0.7]

    metrics_05 = compute_binary_metrics(y_true, y_prob, threshold=0.5)
    metrics_065 = compute_binary_metrics(y_true, y_prob, threshold=0.65)

    assert metrics_05["confusion_matrix"] == {"tn": 1, "fp": 0, "fn": 0, "tp": 2}
    assert metrics_05["predicted_positive_count"] == 2
    assert metrics_05["predicted_negative_count"] == 1

    assert metrics_065["confusion_matrix"] == {"tn": 1, "fp": 0, "fn": 1, "tp": 1}
    assert metrics_065["predicted_positive_count"] == 1
    assert metrics_065["predicted_negative_count"] == 2


def test_auc_none_when_single_class():
    metrics = compute_binary_metrics(
        y_true=[0, 0, 0],
        y_prob=[0.1, 0.2, 0.3],
    )

    assert metrics["auc"] is None
    assert "auc is None because y_true contains only one class" in metrics["warnings"]


def test_no_predicted_positive_warning():
    metrics = compute_binary_metrics(
        y_true=[0, 1, 1],
        y_prob=[0.1, 0.2, 0.3],
        threshold=0.5,
    )

    assert metrics["predicted_positive_count"] == 0
    assert metrics["precision"] == 0.0
    assert (
        "precision is set to 0.0 because there are no predicted positive samples"
        in metrics["warnings"]
    )


def test_no_positive_samples_warning():
    metrics = compute_binary_metrics(
        y_true=[0, 0, 0],
        y_prob=[0.1, 0.2, 0.9],
    )

    assert metrics["recall"] == 0.0
    assert "recall is set to 0.0 because there are no positive samples" in metrics["warnings"]


def test_accept_torch_tensor_inputs():
    torch = pytest.importorskip("torch")

    y_true = torch.tensor([0, 1, 1])
    y_prob = torch.tensor([0.1, 0.8, 0.9])

    metrics = compute_binary_metrics(y_true, y_prob)

    assert metrics["accuracy"] == 1.0
    assert metrics["confusion_matrix"] == {"tn": 1, "fp": 0, "fn": 0, "tp": 2}


def test_invalid_y_true_dimension():
    with pytest.raises(ValueError, match="y_true 必须是一维数组"):
        compute_binary_metrics([[0, 1]], [0.2, 0.8])


def test_invalid_y_prob_dimension():
    with pytest.raises(ValueError, match="y_prob 必须是一维数组"):
        compute_binary_metrics([0, 1], [[0.2, 0.8]])


def test_length_mismatch():
    with pytest.raises(ValueError, match="y_true 和 y_prob 长度必须一致"):
        compute_binary_metrics([0, 1], [0.2])


def test_empty_input():
    with pytest.raises(ValueError, match="y_true 和 y_prob 不能为空"):
        compute_binary_metrics([], [])


def test_invalid_label_values():
    with pytest.raises(ValueError, match="y_true 只能包含 0/1 标签"):
        compute_binary_metrics([0, 1, 2], [0.1, 0.8, 0.9])

    with pytest.raises(ValueError, match="y_true 只能包含 0/1 标签"):
        compute_binary_metrics([0, 1, -1], [0.1, 0.8, 0.9])


def test_y_prob_nan_or_inf():
    with pytest.raises(ValueError, match="y_prob 不能包含 NaN 或 inf"):
        compute_binary_metrics([0, 1], [0.1, np.nan])

    with pytest.raises(ValueError, match="y_prob 不能包含 NaN 或 inf"):
        compute_binary_metrics([0, 1], [0.1, np.inf])


def test_y_prob_out_of_range():
    with pytest.raises(ValueError, match="y_prob 必须位于 \\[0, 1\\] 范围内"):
        compute_binary_metrics([0, 1], [-0.1, 0.8])

    with pytest.raises(ValueError, match="y_prob 必须位于 \\[0, 1\\] 范围内"):
        compute_binary_metrics([0, 1], [0.1, 1.2])


@pytest.mark.parametrize("threshold", [0, 1, -0.1, 1.2, float("nan"), True, "0.5"])
def test_invalid_threshold(threshold):
    with pytest.raises(ValueError, match="threshold 必须位于 0 到 1 之间"):
        compute_binary_metrics([0, 1], [0.2, 0.8], threshold=threshold)