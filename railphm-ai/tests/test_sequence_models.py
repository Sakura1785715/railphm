import pytest
import torch

from app.models import (
    BiLSTMAttentionClassifier,
    BiLSTMClassifier,
    LSTMAttentionClassifier,
    LSTMClassifier,
    TemporalAttention,
    build_sequence_model,
)


def test_temporal_attention_shape_and_weight_sum():
    batch_size = 4
    window_size = 30
    hidden_dim = 64
    attention = TemporalAttention(attention_dim=hidden_dim)
    x = torch.randn(batch_size, window_size, hidden_dim)

    context, attention_weights = attention(x)

    assert context.shape == (batch_size, hidden_dim)
    assert attention_weights.shape == (batch_size, window_size)
    assert torch.allclose(
        attention_weights.sum(dim=1),
        torch.ones(batch_size),
        atol=1e-6,
    )


def test_lstm_classifier_forward_shape():
    model = LSTMClassifier(input_dim=25, hidden_dim=32, num_layers=1, dropout=0.2)
    x = torch.randn(8, 30, 25)

    logits = model(x)

    assert logits.shape == (8,)


def test_bilstm_classifier_forward_shape():
    model = BiLSTMClassifier(input_dim=25, hidden_dim=32, num_layers=1, dropout=0.2)
    x = torch.randn(8, 30, 25)

    logits = model(x)

    assert logits.shape == (8,)


def test_lstm_attention_classifier_forward_shape_and_attention_weights():
    model = LSTMAttentionClassifier(
        input_dim=25,
        hidden_dim=32,
        num_layers=1,
        dropout=0.2,
    )
    x = torch.randn(8, 30, 25)

    logits = model(x)
    logits_with_attention, attention_weights = model(x, return_attention=True)

    assert logits.shape == (8,)
    assert logits_with_attention.shape == (8,)
    assert attention_weights.shape == (8, 30)
    assert torch.allclose(
        attention_weights.sum(dim=1),
        torch.ones(8),
        atol=1e-6,
    )


def test_bilstm_attention_classifier_forward_shape_and_attention_weights():
    model = BiLSTMAttentionClassifier(
        input_dim=25,
        hidden_dim=32,
        num_layers=1,
        dropout=0.2,
    )
    x = torch.randn(8, 30, 25)

    logits = model(x)
    logits_with_attention, attention_weights = model(x, return_attention=True)

    assert logits.shape == (8,)
    assert logits_with_attention.shape == (8,)
    assert attention_weights.shape == (8, 30)
    assert torch.allclose(
        attention_weights.sum(dim=1),
        torch.ones(8),
        atol=1e-6,
    )


def test_batch_size_one_keeps_vector_shape_for_non_attention_model():
    model = LSTMClassifier(input_dim=25, hidden_dim=32, num_layers=1, dropout=0.2)
    x = torch.randn(1, 30, 25)

    logits = model(x)

    assert logits.shape == (1,)


def test_batch_size_one_keeps_vector_shape_for_attention_model():
    model = BiLSTMAttentionClassifier(
        input_dim=25,
        hidden_dim=32,
        num_layers=1,
        dropout=0.2,
    )
    x = torch.randn(1, 30, 25)

    logits = model(x)
    logits_with_attention, attention_weights = model(x, return_attention=True)

    assert logits.shape == (1,)
    assert logits_with_attention.shape == (1,)
    assert attention_weights.shape == (1, 30)


@pytest.mark.parametrize(
    "model_class",
    [
        LSTMClassifier,
        BiLSTMClassifier,
        LSTMAttentionClassifier,
        BiLSTMAttentionClassifier,
    ],
)
def test_forward_rejects_non_3d_input(model_class):
    model = model_class(input_dim=25)

    with pytest.raises(ValueError, match="3D"):
        model(torch.randn(8, 25))


@pytest.mark.parametrize(
    "model_class",
    [
        LSTMClassifier,
        BiLSTMClassifier,
        LSTMAttentionClassifier,
        BiLSTMAttentionClassifier,
    ],
)
def test_forward_rejects_input_dim_mismatch(model_class):
    model = model_class(input_dim=25)

    with pytest.raises(ValueError, match="input_dim mismatch"):
        model(torch.randn(8, 30, 24))


def test_forward_rejects_non_tensor_input():
    model = LSTMClassifier(input_dim=25)

    with pytest.raises(ValueError, match="torch.Tensor"):
        model([[[1.0] * 25] * 30])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"input_dim": 0},
        {"input_dim": True},
        {"input_dim": 25, "hidden_dim": 0},
        {"input_dim": 25, "num_layers": 0},
        {"input_dim": 25, "dropout": 1.0},
        {"input_dim": 25, "dropout": -0.1},
    ],
)
def test_invalid_initialization_args(kwargs):
    with pytest.raises(ValueError):
        LSTMClassifier(**kwargs)


@pytest.mark.parametrize("bad_attention_dim", [0, -1, True])
def test_temporal_attention_rejects_invalid_attention_dim(bad_attention_dim):
    with pytest.raises(ValueError):
        TemporalAttention(bad_attention_dim)


def test_temporal_attention_rejects_invalid_forward_input():
    attention = TemporalAttention(attention_dim=64)

    with pytest.raises(ValueError, match="3D"):
        attention(torch.randn(4, 64))

    with pytest.raises(ValueError, match="attention_dim mismatch"):
        attention(torch.randn(4, 30, 32))


@pytest.mark.parametrize(
    "model_class, expected_name, expected_bidirectional, expected_attention",
    [
        (LSTMClassifier, "LSTMClassifier", False, False),
        (BiLSTMClassifier, "BiLSTMClassifier", True, False),
        (LSTMAttentionClassifier, "LSTMAttentionClassifier", False, True),
        (BiLSTMAttentionClassifier, "BiLSTMAttentionClassifier", True, True),
    ],
)
def test_get_config(
    model_class,
    expected_name,
    expected_bidirectional,
    expected_attention,
):
    model = model_class(input_dim=28, hidden_dim=64, num_layers=1, dropout=0.2)

    config = model.get_config()

    assert config == {
        "name": expected_name,
        "input_dim": 28,
        "hidden_dim": 64,
        "num_layers": 1,
        "dropout": 0.2,
        "bidirectional": expected_bidirectional,
        "attention": expected_attention,
    }


@pytest.mark.parametrize(
    "model_name, expected_class",
    [
        ("lstm", LSTMClassifier),
        ("bilstm", BiLSTMClassifier),
        ("lstm_attention", LSTMAttentionClassifier),
        ("bilstm_attention", BiLSTMAttentionClassifier),
    ],
)
def test_build_sequence_model_returns_expected_model(model_name, expected_class):
    model = build_sequence_model(
        model_name=model_name,
        input_dim=25,
        hidden_dim=32,
        num_layers=1,
        dropout=0.2,
    )

    assert isinstance(model, expected_class)
    assert model.input_dim == 25
    assert model.hidden_dim == 32


def test_build_sequence_model_rejects_invalid_name():
    with pytest.raises(
        ValueError,
        match="lstm|bilstm|lstm_attention|bilstm_attention",
    ):
        build_sequence_model("unknown", input_dim=25)