#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Create a shuffled-label copy of a RailPHM window dataset for sanity check."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir

    if not input_dir.exists():
        raise FileNotFoundError(f"输入数据集目录不存在: {input_dir}")

    if not (input_dir / "y.npy").exists():
        raise FileNotFoundError(f"输入数据集缺少 y.npy: {input_dir / 'y.npy'}")

    if output_dir.exists():
        if not args.overwrite:
            raise FileExistsError(f"输出目录已存在: {output_dir}")
        shutil.rmtree(output_dir)

    shutil.copytree(input_dir, output_dir)

    y = np.load(input_dir / "y.npy")
    rng = np.random.default_rng(args.seed)

    y_shuffled = y.copy()
    rng.shuffle(y_shuffled)

    np.save(output_dir / "y.npy", y_shuffled)

    summary_path = output_dir / "dataset_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}

    summary["label_shuffle"] = {
        "enabled": True,
        "seed": args.seed,
        "source_dataset_dir": str(input_dir),
        "positive_count_before": int(y.sum()),
        "positive_count_after": int(y_shuffled.sum()),
        "sample_count": int(len(y_shuffled)),
        "note": "This dataset is only for sanity check. Do not use it as a real training dataset.",
    }

    save_json(summary_path, summary)

    print("Shuffled label dataset created.")
    print(f"input_dir: {input_dir}")
    print(f"output_dir: {output_dir}")
    print(f"sample_count: {len(y_shuffled)}")
    print(f"positive_count_before: {int(y.sum())}")
    print(f"positive_count_after: {int(y_shuffled.sum())}")


if __name__ == "__main__":
    main()
