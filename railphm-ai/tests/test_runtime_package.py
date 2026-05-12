def test_runtime_package_importable():
    import app.runtime

    assert app.runtime.__all__ == []


def test_artifact_manifest_constants():
    from app.runtime.artifact_manifest import (
        DEFAULT_MANIFEST_FILENAME,
        OPTIONAL_RUNTIME_ARTIFACTS,
        REQUIRED_RUNTIME_ARTIFACTS,
    )

    assert DEFAULT_MANIFEST_FILENAME == "model_artifact_manifest.json"

    assert "model_weight" in REQUIRED_RUNTIME_ARTIFACTS
    assert "training_config" in REQUIRED_RUNTIME_ARTIFACTS
    assert "feature_columns" in REQUIRED_RUNTIME_ARTIFACTS

    assert "evaluation_summary" in OPTIONAL_RUNTIME_ARTIFACTS
    assert "metrics_history" in OPTIONAL_RUNTIME_ARTIFACTS


def test_model_loader_constants():
    from app.runtime.model_loader import (
        DEFAULT_MODEL_VERSION,
        SUPPORTED_RUNTIME_MODELS,
    )

    assert DEFAULT_MODEL_VERSION == "bilstm_attention_h1_full_features"
    assert SUPPORTED_RUNTIME_MODELS["bilstm_attention"] == "BiLSTMAttentionClassifier"