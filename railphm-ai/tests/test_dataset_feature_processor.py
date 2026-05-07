# tests/test_dataset_feature_processor.py

import numpy as np
import pandas as pd

from app.dataset.feature_processor import FeatureProcessor


def test_feature_processor_transforms_numeric_features_without_nan():
    df = pd.DataFrame(
        {
            "数据时间": [
                "20150109112305",
                "20150109112306",
                "20150109112307",
                "20150109112308",
            ],
            "报警部位": ["", "", "车载主机", ""],
            "报警部位.1": ["不应进入模型", "", "", ""],
            "报警部位.2": ["", "也不应进入模型", "", ""],
            "唯一标识": ["uid-0", "uid-1", "uid-2", "uid-3"],
            "司机手机号": ["13800000000", "13800000001", "13800000002", "13800000003"],
            "速度": ["10", None, "30", "bad"],
            "里程": [100, 101, None, 103],
            "运行距离": [5, 5, 5, 5],
            "司机操作是否合规": ["True", "False", "", None],
        }
    )

    processor = FeatureProcessor(
        feature_columns=[
            "速度",
            "里程",
            "运行距离",
            "报警部位",
            "报警部位.1",
            "报警部位.2",
            "司机手机号",
            "不存在列",
            "司机操作是否合规",
        ]
    )

    result = processor.transform(df)

    assert result.feature_matrix.shape == (4, 5)
    assert result.feature_matrix.dtype == np.float32
    assert not np.isnan(result.feature_matrix).any()

    assert "速度" in result.feature_columns
    assert "里程" in result.feature_columns
    assert "运行距离" in result.feature_columns
    assert "不存在列" in result.feature_columns
    assert "司机操作是否合规" in result.feature_columns

    assert "报警部位" not in result.feature_columns
    assert "报警部位.1" not in result.feature_columns
    assert "报警部位.2" not in result.feature_columns
    assert "司机手机号" not in result.feature_columns

    assert "不存在列" in result.missing_feature_columns

    expected = np.array(
        [
            [10.0, 100.0, 5.0, 0.0, 1.0],
            [20.0, 101.0, 5.0, 0.0, 0.0],
            [30.0, 102.0, 5.0, 0.0, 0.0],
            [30.0, 103.0, 5.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(result.feature_matrix, expected)

    running_distance_index = result.feature_columns.index("运行距离")
    assert np.all(result.feature_matrix[:, running_distance_index] == 5.0)


def test_feature_processor_default_columns_exclude_label_and_sensitive_fields():
    df = pd.DataFrame(
        {
            "数据时间": ["20150109112305", "20150109112306"],
            "报警部位": ["车载主机", ""],
            "报警部位.1": ["不应作为标签", ""],
            "报警部位.2": ["也不应作为标签", ""],
            "唯一标识": ["uid-0", "uid-1"],
            "司机名": ["张三", "李四"],
            "司机手机号": ["13800000000", "13800000001"],
            "速度": [100, 101],
            "里程": [200, 201],
            "运行距离": [300, 301],
            "室外温度": [20, 21],
            "湿度": [50, 51],
        }
    )

    processor = FeatureProcessor()
    result = processor.transform(df)

    assert result.feature_matrix.shape[0] == 2
    assert result.feature_matrix.dtype == np.float32
    assert not np.isnan(result.feature_matrix).any()

    forbidden_columns = {
        "报警部位",
        "报警部位.1",
        "报警部位.2",
        "唯一标识",
        "司机名",
        "司机手机号",
    }

    assert forbidden_columns.isdisjoint(set(result.feature_columns))


def test_feature_processor_records_all_nan_existing_columns():
    df = pd.DataFrame(
        {
            "速度": [None, None, None],
            "里程": [1, 2, 3],
        }
    )

    processor = FeatureProcessor(feature_columns=["速度", "里程"])
    result = processor.transform(df)

    assert "速度" in result.all_nan_feature_columns
    assert result.feature_matrix.shape == (3, 2)
    assert not np.isnan(result.feature_matrix).any()

    speed_index = result.feature_columns.index("速度")
    assert np.all(result.feature_matrix[:, speed_index] == 0.0)