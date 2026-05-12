#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir

    if output_dir.exists():
        if not args.overwrite:
            raise FileExistsError(f"输出目录已存在: {output_dir}")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    X = np.load(input_dir / "X.npy")
    y = np.load(input_dir / "y.npy")
    manifest = pd.read_csv(input_dir / "window_manifest.csv", encoding="utf-8-sig")

    if len(manifest) != len(y) or X.shape[0] != len(y):
        raise ValueError("X/y/manifest 样本数不一致")

    seg_ratio = manifest.groupby("segment_id")["label"].mean()
    mixed_segment_ids = set(seg_ratio[(seg_ratio > 0) & (seg_ratio < 1)].index)

    keep_mask = manifest["segment_id"].isin(mixed_segment_ids).to_numpy()
    keep_indices = np.flatnonzero(keep_mask)

    X_new = X[keep_indices]
    y_new = y[keep_indices]
    manifest_new = manifest.iloc[keep_indices].reset_index(drop=True)

    np.save(output_dir / "X.npy", X_new)
    np.save(output_dir / "y.npy", y_new)
    manifest_new.to_csv(output_dir / "window_manifest.csv", index=False, encoding="utf-8-sig")

    for name in ["feature_columns.json"]:
        src = input_dir / name
        if src.exists():
            shutil.copy2(src, output_dir / name)

    summary = {
        "source_dataset_dir": str(input_dir),
        "dataset_type": "mixed_only",
        "total_samples_before": int(len(y)),
        "total_samples_after": int(len(y_new)),
        "kept_segment_count": int(len(mixed_segment_ids)),
        "positive_count": int(y_new.sum()),
        "negative_count": int(len(y_new) - y_new.sum()),
        "positive_ratio": float(y_new.mean()) if len(y_new) else 0.0,
        "X_shape": list(X_new.shape),
        "y_shape": list(y_new.shape),
        "note": "Only segments with 0 < positive_ratio < 1 are kept. Splits must be rebuilt after this step.",
    }

    save_json(output_dir / "dataset_summary.json", summary)

    print("Mixed-only dataset created.")
    print(f"input_dir: {input_dir}")
    print(f"output_dir: {output_dir}")
    print(f"kept_segment_count: {len(mixed_segment_ids)}")
    print(f"samples_before: {len(y)}")
    print(f"samples_after: {len(y_new)}")
    print(f"positive_ratio_after: {summary['positive_ratio']:.6f}")


if __name__ == "__main__":
    main()