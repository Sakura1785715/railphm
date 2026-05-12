"""
二分类风险预测指标计算。

compute_binary_metrics 函数，用于计算二分类模型在风险预测任务上的常用评价指标。
输入真实标签（0/1）和模型预测概率（[0,1] 区间），根据指定的阈值生成预测类别，返回以下指标：
- accuracy（准确率）
- precision（精确率）
- recall（召回率）
- f1（F1 分数）
- auc（ROC-AUC 分数，若只有单类别则返回 None）
- brier_score（Brier 分数）
- threshold（使用的概率阈值）
- positive_count / negative_count（真实正/负样本数）
- predicted_positive_count / predicted_negative_count（预测正/负样本数）
- confusion_matrix（混淆矩阵：tn, fp, fn, tp）
- warnings（计算过程中产生的警告信息列表）
"""
import numbers
from typing import Any, Dict, List

import numpy as np
from sklearn.metrics import roc_auc_score


def compute_binary_metrics(
    y_true: Any,
    y_prob: Any,
    threshold: float = 0.5,
) -> Dict[str, object]:
    """
    计算二分类风险预测指标。

    y_true: 真实标签，取值只能为 0/1。
    y_prob: 模型输出的正类概率，取值范围必须在 [0, 1]。
    threshold: 概率阈值，y_prob >= threshold 判为正类。
    """
    _validate_threshold(threshold)

    y_true_array = _to_numpy_array(y_true)
    y_prob_array = _to_numpy_array(y_prob)

    if y_true_array.ndim != 1:
        raise ValueError("y_true 必须是一维数组")

    if y_prob_array.ndim != 1:
        raise ValueError("y_prob 必须是一维数组")

    if y_true_array.size == 0 or y_prob_array.size == 0:
        raise ValueError("y_true 和 y_prob 不能为空")

    if y_true_array.shape[0] != y_prob_array.shape[0]:
        raise ValueError("y_true 和 y_prob 长度必须一致")

    if not np.isin(y_true_array, [0, 1]).all():
        raise ValueError("y_true 只能包含 0/1 标签")

    try:
        y_prob_array = y_prob_array.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("y_prob 必须位于 [0, 1] 范围内") from exc

    if not np.isfinite(y_prob_array).all():
        raise ValueError("y_prob 不能包含 NaN 或 inf")

    if (y_prob_array < 0).any() or (y_prob_array > 1).any():
        raise ValueError("y_prob 必须位于 [0, 1] 范围内")

    y_true_array = y_true_array.astype(np.int64)
    y_pred_array = (y_prob_array >= float(threshold)).astype(np.int64)

    tn = int(((y_true_array == 0) & (y_pred_array == 0)).sum())
    fp = int(((y_true_array == 0) & (y_pred_array == 1)).sum())
    fn = int(((y_true_array == 1) & (y_pred_array == 0)).sum())
    tp = int(((y_true_array == 1) & (y_pred_array == 1)).sum())

    total = int(y_true_array.shape[0])
    positive_count = int((y_true_array == 1).sum())
    negative_count = int((y_true_array == 0).sum())
    predicted_positive_count = int((y_pred_array == 1).sum())
    predicted_negative_count = int((y_pred_array == 0).sum())

    warnings: List[str] = []

    accuracy = float((tp + tn) / total)

    precision_denominator = tp + fp
    if precision_denominator == 0:
        precision = 0.0
        warnings.append(
            "precision is set to 0.0 because there are no predicted positive samples"
        )
    else:
        precision = float(tp / precision_denominator)

    recall_denominator = tp + fn
    if recall_denominator == 0:
        recall = 0.0
        warnings.append("recall is set to 0.0 because there are no positive samples")
    else:
        recall = float(tp / recall_denominator)

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = float(2 * precision * recall / (precision + recall))

    brier_score = float(np.mean((y_prob_array - y_true_array) ** 2))

    if np.unique(y_true_array).size < 2:
        auc = None
        warnings.append("auc is None because y_true contains only one class")
    else:
        auc = float(roc_auc_score(y_true_array, y_prob_array))

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc": auc,
        "brier_score": float(brier_score),
        "threshold": float(threshold),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "predicted_positive_count": predicted_positive_count,
        "predicted_negative_count": predicted_negative_count,
        "confusion_matrix": {
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
        },
        "warnings": warnings,
    }


def _to_numpy_array(values: Any) -> np.ndarray:
    """
    将 list / tuple / np.ndarray / torch.Tensor 转换为 numpy.ndarray。
    这里不直接 import torch，避免 metrics 模块产生额外副作用。
    """
    if hasattr(values, "detach") and hasattr(values, "cpu"):
        values = values.detach().cpu().numpy()

    return np.asarray(values)


def _validate_threshold(threshold: float) -> None:
    if isinstance(threshold, bool) or not isinstance(threshold, numbers.Real):
        raise ValueError("threshold 必须位于 0 到 1 之间")

    if not np.isfinite(float(threshold)) or not (0 < float(threshold) < 1):
        raise ValueError("threshold 必须位于 0 到 1 之间")