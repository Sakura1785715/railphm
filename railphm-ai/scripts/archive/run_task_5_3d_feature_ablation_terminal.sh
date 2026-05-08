#!/usr/bin/env bash
set -euo pipefail

SEGMENTS_DIR=""
OVERWRITE_FLAG=""

PROFILES=("full_features" "remove_id_like_features" "continuous_only_features")
WINDOW_SIZE=30
STRIDE=1
HORIZON=1
CONDITION_K=3
SEED=42
EPOCHS=30
BATCH_SIZE=256
LR=0.001
DEVICE="auto"
MODEL="bilstm_attention"
BEST_METRIC="val_auc"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_task_5_3d_feature_ablation_terminal.sh \
    --segments-dir "/path/to/atp_segments_v1" \
    [--overwrite]

Purpose:
  Task 5-3d feature ablation for ID-like fields.
  Fixed:
    window_size=30
    stride=1
    horizon=1
    model=bilstm_attention
  Profiles:
    full_features
    remove_id_like_features
    continuous_only_features
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --segments-dir)
      SEGMENTS_DIR="$2"
      shift 2
      ;;
    --overwrite)
      OVERWRITE_FLAG="--overwrite"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$SEGMENTS_DIR" ]]; then
  echo "[ERROR] --segments-dir is required." >&2
  usage
  exit 1
fi

if [[ ! -d "$SEGMENTS_DIR" ]]; then
  echo "[ERROR] segments dir does not exist: $SEGMENTS_DIR" >&2
  exit 1
fi

echo "============================================================"
echo "RailPHM Task 5-3d: feature ablation terminal experiment"
echo "segments_dir: $SEGMENTS_DIR"
echo "profiles: ${PROFILES[*]}"
echo "window_size: $WINDOW_SIZE"
echo "stride: $STRIDE"
echo "horizon: $HORIZON"
echo "model: $MODEL"
echo "condition_k: $CONDITION_K"
echo "epochs: $EPOCHS"
echo "overwrite: ${OVERWRITE_FLAG:-false}"
echo "============================================================"

for PROFILE in "${PROFILES[@]}"; do
  RAW_DIR="data/datasets/sim_window_w${WINDOW_SIZE}_s${STRIDE}_h${HORIZON}_${PROFILE}"
  SCALED_DIR="data/datasets/sim_window_w${WINDOW_SIZE}_s${STRIDE}_h${HORIZON}_${PROFILE}_train_scaled"
  CONDITION_DIR="data/datasets/sim_window_w${WINDOW_SIZE}_s${STRIDE}_h${HORIZON}_${PROFILE}_train_scaled_condition_k${CONDITION_K}"
  RUN_DIR="outputs/sequence_models/bilstm_attention_h${HORIZON}_${PROFILE}"

  echo
  echo "============================================================"
  echo "[${PROFILE}] 1/9 Build window dataset"
  echo "============================================================"
  python scripts/build_window_dataset.py \
    --segments-dir "$SEGMENTS_DIR" \
    --output-dir "$RAW_DIR" \
    --window-size "$WINDOW_SIZE" \
    --stride "$STRIDE" \
    --horizon "$HORIZON" \
    --feature-profile "$PROFILE" \
    $OVERWRITE_FLAG \
    --verbose

  echo
  echo "============================================================"
  echo "[${PROFILE}] 2/9 Inspect raw dataset"
  echo "============================================================"
  python scripts/inspect_dataset.py \
    --dataset-dir "$RAW_DIR"

  echo
  echo "============================================================"
  echo "[${PROFILE}] 3/9 Split dataset by segment_id"
  echo "============================================================"
  python scripts/split_dataset.py \
    --dataset-dir "$RAW_DIR" \
    --train-ratio 0.7 \
    --val-ratio 0.15 \
    --test-ratio 0.15 \
    --seed "$SEED" \
    $OVERWRITE_FLAG

  echo
  echo "============================================================"
  echo "[${PROFILE}] 4/9 Train-only standard scaling"
  echo "============================================================"
  python scripts/scale_window_dataset.py \
    --input-dir "$RAW_DIR" \
    --output-dir "$SCALED_DIR" \
    --method standard \
    $OVERWRITE_FLAG

  echo
  echo "============================================================"
  echo "[${PROFILE}] 5/9 Inspect scaled dataset"
  echo "============================================================"
  python scripts/inspect_dataset.py \
    --dataset-dir "$SCALED_DIR"

  echo
  echo "============================================================"
  echo "[${PROFILE}] 6/9 K-means condition clustering"
  echo "============================================================"
  python scripts/cluster_conditions.py \
    --dataset-dir "$SCALED_DIR" \
    --n-clusters "$CONDITION_K" \
    --seed "$SEED" \
    $OVERWRITE_FLAG \
    --verbose

  echo
  echo "============================================================"
  echo "[${PROFILE}] 7/9 Build condition one-hot augmented dataset"
  echo "============================================================"
  python scripts/build_condition_augmented_dataset.py \
    --input-dir "$SCALED_DIR" \
    --output-dir "$CONDITION_DIR" \
    $OVERWRITE_FLAG \
    --verbose

  echo
  echo "============================================================"
  echo "[${PROFILE}] 8/9 Inspect condition augmented dataset"
  echo "============================================================"
  python scripts/inspect_dataset.py \
    --dataset-dir "$CONDITION_DIR"

  echo
  echo "============================================================"
  echo "[${PROFILE}] 9/9 Train Bi-LSTM+Attention"
  echo "============================================================"
  python scripts/train_sequence_model.py \
    --dataset-dir "$CONDITION_DIR" \
    --output-dir "$RUN_DIR" \
    --model "$MODEL" \
    --epochs "$EPOCHS" \
    --batch-size "$BATCH_SIZE" \
    --lr "$LR" \
    --seed "$SEED" \
    --device "$DEVICE" \
    --threshold 0.5 \
    --hidden-dim 64 \
    --num-layers 1 \
    --dropout 0.2 \
    --best-metric "$BEST_METRIC" \
    $OVERWRITE_FLAG

  echo
  echo "[${PROFILE}] Finished."
  echo "condition dataset: $CONDITION_DIR"
  echo "run dir: $RUN_DIR"
done

echo
echo "============================================================"
echo "Task 5-3d training finished."
echo "Next: run scripts/print_feature_ablation_diagnosis.py"
echo "============================================================"