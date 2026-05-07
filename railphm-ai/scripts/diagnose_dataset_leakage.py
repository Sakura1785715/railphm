#!/usr/bin/env python3
"""
RailPHM 窗口数据集泄露诊断脚本。

本脚本只做诊断，不训练模型，不修改数据集。
重点检查：
1. X/y/manifest/splits 基础一致性；
2. train/val/test indices 是否重叠；
3. train/val/test segment_id 是否重叠；
4. y 是否与 window_manifest.csv 中 label 一致；
5. target_row 与 window_end_row 是否符合 prediction_horizon；
6. 单个特征在 first_step / last_step / mean / max / min / std / delta 上是否能几乎直接预测 y；
7. 标签在 segment 内是否高度连续；
8. 输出可疑字段和 top single-feature AUC 排名。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SUSPICIOUS_KEYWORDS = [
    "报警",
    "告警",
    "故障",
    "异常",
    "等级",
    "制动",
    "合规",
    "状态",
    "label",
    "alarm",
    "fault",
    "warning",
    "risk",
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def directionless_auc(y_true, values):
    unique_y = np.unique(y_true)
    unique_v = np.unique(values)

    if unique_y.size < 2 or unique_v.size < 2:
        return None

    auc = roc_auc_score(y_true, values)
    return float(max(auc, 1.0 - auc))


def safe_ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def summarize_split(name, indices, y, manifest):
    part_y = y[indices]
    part_manifest = manifest.iloc[indices]

    positive_count = int(part_y.sum())
    sample_count = int(len(indices))
    negative_count = sample_count - positive_count

    return {
        "name": name,
        "sample_count": sample_count,
        "segment_count": int(part_manifest["segment_id"].nunique()) if "segment_id" in part_manifest.columns else None,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "positive_ratio": safe_ratio(positive_count, sample_count),
    }


def check_split_integrity(train_indices, val_indices, test_indices, total_samples):
    train_set = set(train_indices.tolist())
    val_set = set(val_indices.tolist())
    test_set = set(test_indices.tolist())

    all_indices = np.concatenate([train_indices, val_indices, test_indices])
    unique_indices = np.unique(all_indices)

    return {
        "train_val_index_overlap": len(train_set.intersection(val_set)),
        "train_test_index_overlap": len(train_set.intersection(test_set)),
        "val_test_index_overlap": len(val_set.intersection(test_set)),
        "all_indices_count": int(all_indices.shape[0]),
        "unique_indices_count": int(unique_indices.shape[0]),
        "total_samples": int(total_samples),
        "has_duplicate_or_missing_index": bool(unique_indices.shape[0] != total_samples or all_indices.shape[0] != total_samples),
        "min_index": int(all_indices.min()),
        "max_index": int(all_indices.max()),
        "index_out_of_range": bool(all_indices.min() < 0 or all_indices.max() >= total_samples),
    }


def check_segment_overlap(manifest, train_indices, val_indices, test_indices):
    if "segment_id" not in manifest.columns:
        return {
            "error": "window_manifest.csv 缺少 segment_id",
        }

    train_segments = set(manifest.iloc[train_indices]["segment_id"].astype(str).tolist())
    val_segments = set(manifest.iloc[val_indices]["segment_id"].astype(str).tolist())
    test_segments = set(manifest.iloc[test_indices]["segment_id"].astype(str).tolist())

    train_val = train_segments.intersection(val_segments)
    train_test = train_segments.intersection(test_segments)
    val_test = val_segments.intersection(test_segments)

    return {
        "train_segment_count": len(train_segments),
        "val_segment_count": len(val_segments),
        "test_segment_count": len(test_segments),
        "train_val_segment_overlap": len(train_val),
        "train_test_segment_overlap": len(train_test),
        "val_test_segment_overlap": len(val_test),
        "has_segment_leakage": bool(train_val or train_test or val_test),
        "examples": {
            "train_val": sorted(list(train_val))[:10],
            "train_test": sorted(list(train_test))[:10],
            "val_test": sorted(list(val_test))[:10],
        },
    }


def check_manifest_label_consistency(y, manifest):
    if "label" not in manifest.columns:
        return {
            "error": "window_manifest.csv 缺少 label 列",
        }

    manifest_label = manifest["label"].astype(int).to_numpy()
    mismatch = np.flatnonzero(manifest_label != y.astype(int))

    return {
        "mismatch_count": int(mismatch.shape[0]),
        "mismatch_ratio": safe_ratio(int(mismatch.shape[0]), int(y.shape[0])),
        "mismatch_examples": mismatch[:20].astype(int).tolist(),
    }


def check_horizon(manifest):
    required = {"window_end_row", "target_row"}
    if not required.issubset(set(manifest.columns)):
        return {
            "error": "window_manifest.csv 缺少 window_end_row 或 target_row",
        }

    delta = manifest["target_row"].astype(int) - manifest["window_end_row"].astype(int)

    return {
        "target_minus_window_end_min": int(delta.min()),
        "target_minus_window_end_max": int(delta.max()),
        "target_minus_window_end_unique": sorted(delta.unique().astype(int).tolist())[:20],
        "is_constant_horizon": bool(delta.nunique() == 1),
    }


def check_suspicious_feature_names(feature_columns):
    suspects = []
    for idx, col in enumerate(feature_columns):
        lower_col = str(col).lower()
        hit_keywords = [
            keyword for keyword in SUSPICIOUS_KEYWORDS
            if keyword.lower() in lower_col
        ]
        if hit_keywords:
            suspects.append(
                {
                    "feature_index": idx,
                    "feature_name": col,
                    "hit_keywords": hit_keywords,
                }
            )
    return suspects


def build_feature_views(X):
    return {
        "first_step": X[:, 0, :],
        "last_step": X[:, -1, :],
        "window_mean": X.mean(axis=1),
        "window_max": X.max(axis=1),
        "window_min": X.min(axis=1),
        "window_std": X.std(axis=1),
        "delta_last_first": X[:, -1, :] - X[:, 0, :],
    }


def single_feature_auc_report(X, y, indices, feature_columns, split_name, top_n=50):
    y_part = y[indices]
    X_part = X[indices]

    rows = []
    views = build_feature_views(X_part)

    for view_name, matrix in views.items():
        for feature_idx, feature_name in enumerate(feature_columns):
            values = matrix[:, feature_idx]
            auc = directionless_auc(y_part, values)
            if auc is None:
                continue

            rows.append(
                {
                    "split": split_name,
                    "view": view_name,
                    "feature_index": int(feature_idx),
                    "feature_name": str(feature_name),
                    "directionless_auc": float(auc),
                }
            )

    rows.sort(key=lambda item: item["directionless_auc"], reverse=True)
    return rows[:top_n], rows


def label_persistence_report(y, manifest):
    if "segment_id" not in manifest.columns or "target_row" not in manifest.columns:
        return {
            "error": "window_manifest.csv 缺少 segment_id 或 target_row，无法计算标签连续性",
        }

    df = manifest[["segment_id", "target_row"]].copy()
    df["y"] = y.astype(int)
    df = df.sort_values(["segment_id", "target_row"])

    same_prev_total = 0
    same_prev_count = 0
    transition_count = 0

    for _, group in df.groupby("segment_id"):
        labels = group["y"].to_numpy()
        if len(labels) <= 1:
            continue

        prev = labels[:-1]
        curr = labels[1:]

        same_prev_count += int((prev == curr).sum())
        same_prev_total += int(len(curr))
        transition_count += int((prev != curr).sum())

    return {
        "same_as_previous_label_ratio": safe_ratio(same_prev_count, same_prev_total),
        "transition_count": transition_count,
        "comparison_count": same_prev_total,
    }


def write_markdown(path, report):
    lines = [
        "# RailPHM 数据集泄露诊断报告",
        "",
        "## 1. 基础信息",
        "",
        f"- dataset_dir：`{report['dataset_dir']}`",
        f"- X_shape：{report['shape']['X_shape']}",
        f"- y_shape：{report['shape']['y_shape']}",
        f"- feature_dim：{report['shape']['feature_dim']}",
        f"- positive_ratio：{report['shape']['positive_ratio']:.6f}",
        "",
        "## 2. split 完整性检查",
        "",
        "```json",
        json.dumps(report["split_integrity"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 3. segment 重叠检查",
        "",
        "```json",
        json.dumps(report["segment_overlap"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 4. y 与 manifest label 一致性",
        "",
        "```json",
        json.dumps(report["manifest_label_consistency"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 5. horizon 检查",
        "",
        "```json",
        json.dumps(report["horizon_check"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 6. 可疑字段名",
        "",
    ]

    if report["suspicious_feature_names"]:
        for item in report["suspicious_feature_names"]:
            lines.append(
                f"- feature[{item['feature_index']}] {item['feature_name']}，命中关键词：{', '.join(item['hit_keywords'])}"
            )
    else:
        lines.append("- 未发现命中关键词的可疑字段名。")

    lines.extend(
        [
            "",
            "## 7. 单特征 AUC Top 30",
            "",
            "| split | view | feature_index | feature_name | directionless_auc |",
            "|---|---|---:|---|---:|",
        ]
    )

    for item in report["top_single_feature_auc"][:30]:
        lines.append(
            f"| {item['split']} | {item['view']} | {item['feature_index']} | "
            f"{item['feature_name']} | {item['directionless_auc']:.6f} |"
        )

    lines.extend(
        [
            "",
            "## 8. 标签连续性",
            "",
            "```json",
            json.dumps(report["label_persistence"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## 9. 初步判断",
            "",
        ]
    )

    danger_items = []

    if report["split_integrity"]["train_val_index_overlap"] > 0:
        danger_items.append("train 与 val 存在样本索引重叠。")
    if report["split_integrity"]["train_test_index_overlap"] > 0:
        danger_items.append("train 与 test 存在样本索引重叠。")
    if report["split_integrity"]["val_test_index_overlap"] > 0:
        danger_items.append("val 与 test 存在样本索引重叠。")
    if report["segment_overlap"].get("has_segment_leakage"):
        danger_items.append("train / val / test 存在 segment_id 重叠。")
    if report["manifest_label_consistency"].get("mismatch_count", 0) > 0:
        danger_items.append("y.npy 与 window_manifest.csv 中 label 不一致。")

    top_auc = report["top_single_feature_auc"][0]["directionless_auc"] if report["top_single_feature_auc"] else 0
    if top_auc >= 0.98:
        danger_items.append("存在单个特征或单个特征统计量 AUC >= 0.98，强烈疑似标签代理特征泄露。")
    elif top_auc >= 0.95:
        danger_items.append("存在单个特征或单个特征统计量 AUC >= 0.95，需要重点排查强代理字段。")

    persistence = report["label_persistence"].get("same_as_previous_label_ratio")
    if persistence is not None and persistence >= 0.98:
        danger_items.append("segment 内相邻窗口标签高度一致，任务可能过于依赖标签连续性或报警持续区间。")

    if danger_items:
        lines.append("当前数据集存在以下高风险问题：")
        lines.append("")
        for item in danger_items:
            lines.append(f"- {item}")
    else:
        lines.append("未在基础诊断中发现直接泄露，但仍建议继续进行字段消融和更严格 group split 验证。")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/leakage_diagnosis"))
    parser.add_argument("--top-n", type=int, default=50)
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    X = np.load(dataset_dir / "X.npy")
    y = np.load(dataset_dir / "y.npy")
    train_indices = np.load(dataset_dir / "splits" / "train_indices.npy")
    val_indices = np.load(dataset_dir / "splits" / "val_indices.npy")
    test_indices = np.load(dataset_dir / "splits" / "test_indices.npy")
    manifest = pd.read_csv(dataset_dir / "window_manifest.csv", encoding="utf-8-sig")
    feature_columns = load_json(dataset_dir / "feature_columns.json")

    split_integrity = check_split_integrity(
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
        total_samples=X.shape[0],
    )

    segment_overlap = check_segment_overlap(
        manifest=manifest,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
    )

    manifest_label_consistency = check_manifest_label_consistency(y, manifest)
    horizon_check = check_horizon(manifest)
    suspicious_feature_names = check_suspicious_feature_names(feature_columns)
    label_persistence = label_persistence_report(y, manifest)

    top_rows_all = []
    full_rows_all = []

    for split_name, indices in [
        ("train", train_indices),
        ("val", val_indices),
        ("test", test_indices),
    ]:
        top_rows, full_rows = single_feature_auc_report(
            X=X,
            y=y,
            indices=indices,
            feature_columns=feature_columns,
            split_name=split_name,
            top_n=args.top_n,
        )
        top_rows_all.extend(top_rows)
        full_rows_all.extend(full_rows)

    top_rows_all.sort(key=lambda item: item["directionless_auc"], reverse=True)
    full_rows_all.sort(key=lambda item: item["directionless_auc"], reverse=True)

    pd.DataFrame(full_rows_all).to_csv(
        output_dir / "single_feature_auc_full.csv",
        index=False,
        encoding="utf-8-sig",
    )

    report = {
        "dataset_dir": str(dataset_dir),
        "shape": {
            "X_shape": [int(v) for v in X.shape],
            "y_shape": [int(v) for v in y.shape],
            "feature_dim": int(X.shape[2]),
            "positive_count": int(y.sum()),
            "negative_count": int(y.shape[0] - y.sum()),
            "positive_ratio": float(y.mean()),
        },
        "split_summary": {
            "train": summarize_split("train", train_indices, y, manifest),
            "val": summarize_split("val", val_indices, y, manifest),
            "test": summarize_split("test", test_indices, y, manifest),
        },
        "split_integrity": split_integrity,
        "segment_overlap": segment_overlap,
        "manifest_label_consistency": manifest_label_consistency,
        "horizon_check": horizon_check,
        "suspicious_feature_names": suspicious_feature_names,
        "top_single_feature_auc": top_rows_all[: args.top_n],
        "label_persistence": label_persistence,
        "outputs": {
            "diagnosis_json": str(output_dir / "leakage_diagnosis.json"),
            "diagnosis_markdown": str(output_dir / "leakage_diagnosis.md"),
            "single_feature_auc_full": str(output_dir / "single_feature_auc_full.csv"),
        },
    }

    save_json(output_dir / "leakage_diagnosis.json", report)
    write_markdown(output_dir / "leakage_diagnosis.md", report)

    print("Leakage diagnosis finished.")
    print(f"diagnosis_json: {output_dir / 'leakage_diagnosis.json'}")
    print(f"diagnosis_markdown: {output_dir / 'leakage_diagnosis.md'}")
    print(f"single_feature_auc_full: {output_dir / 'single_feature_auc_full.csv'}")

    if top_rows_all:
        top = top_rows_all[0]
        print(
            "top_single_feature_auc: "
            f"{top['directionless_auc']:.6f} | "
            f"{top['split']} | {top['view']} | "
            f"feature[{top['feature_index']}] {top['feature_name']}"
        )


if __name__ == "__main__":
    main()