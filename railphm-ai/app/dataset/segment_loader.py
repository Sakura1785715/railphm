from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import pandas as pd
from app.dataset.feature_config import TIME_COL, TIME_FORMAT


@dataclass
class SegmentData:
    """
    单个 ATP segment CSV 的读取结果。
    - df 保留完整 CSV 字段，不在读取层删列；
    - parsed_time 与 df 行索引一一对应；
    - is_time_continuous 只表示原始行顺序下是否严格 1 秒递增。
    """
    segment_id: str           # 片段的唯一标识（文件名去掉后缀）
    file_name: str            # 完整的文件名（如 segment_001.csv）
    file_path: Path           # 文件的绝对/相对路径对象
    df: pd.DataFrame          # 读取上来的完整原始数据表
    parsed_time: pd.Series    # 转换成 pandas 时间格式后的时间列
    start_time: pd.Timestamp  # 这个片段的起始时间
    end_time: pd.Timestamp    # 这个片段的结束时间
    row_count: int            # 这个片段包含的数据总行数
    is_time_continuous: bool  # 核心标记：这个片段的时间是否严格按 1 秒递增


class SegmentLoader:
    """
    ATP segment 文件读取器。
    1. 完整读取 segment CSV；
    2. 自动处理常见中文 CSV 编码；
    3. 解析“数据时间”；
    4. 检查原始行顺序是否严格 1 秒递增。
    没有做：
    - 特征选择；
    - 缺失值填充；
    - 归一化；
    - 窗口构造；
    - 标签生成。
    """

    ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")

    # 读取csv文件
    def load_segment(self, file_path: Path) -> SegmentData:
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"segment 文件不存在: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"segment 路径不是文件: {file_path}")

        df = self._read_csv_with_fallback(file_path) # 调用内部方法读取CSV为DataFrame

        if TIME_COL not in df.columns:
            raise ValueError(f"segment 文件缺少时间字段 {TIME_COL}: {file_path.name}")

        if df.empty:
            raise ValueError(f"segment 文件为空: {file_path.name}")

        # 重置索引，保证后续窗口构造按 0-based 行号处理。
        df = df.reset_index(drop=True)
        # 解析时间列为Timestamp Series
        parsed_time = self._parse_time_column(df, file_path)
        # 检查时间片段连续性
        is_time_continuous = self._check_strict_one_second_continuity(parsed_time)

        return SegmentData(
            segment_id=file_path.stem, # 不带后缀的文件名
            file_name=file_path.name,  # 带后缀文件名
            file_path=file_path,
            df=df,
            parsed_time=parsed_time,  
            start_time=parsed_time.iloc[0], # 第一个时间戳
            end_time=parsed_time.iloc[-1],  # 最后一个时间戳
            row_count=len(df),
            is_time_continuous=is_time_continuous,
        )
    # 读取目录下所有csv文件，调用oad_segment生成SegmentData对象，返回一个生成器（迭代器）
    def iter_segments(self, segments_dir: Path) -> Iterator[SegmentData]:
        segments_dir = Path(segments_dir)

        if not segments_dir.exists():
            raise FileNotFoundError(f"segment 目录不存在: {segments_dir}")

        if not segments_dir.is_dir():
            raise ValueError(f"segments_dir 不是目录: {segments_dir}")

        for file_path in sorted(segments_dir.glob("segment_*.csv")):
            if not file_path.is_file():
                continue

            yield self.load_segment(file_path)

    def _read_csv_with_fallback(self, file_path: Path) -> pd.DataFrame:
        last_error: Exception | None = None

        for encoding in self.ENCODINGS:
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
            except pd.errors.ParserError as exc:
                raise ValueError(f"CSV 解析失败: {file_path.name}, error={exc}") from exc

        raise UnicodeDecodeError(
            encoding=",".join(self.ENCODINGS),
            object=b"",
            start=0,
            end=1,
            reason=f"无法使用常见编码读取文件: {file_path.name}; last_error={last_error}",
        )
    # 输入DataFrame和文件路径，返回一个由解析后的时间构成的pd.Series里面每个元素是 pd.Timestamp）
    def _parse_time_column(self, df: pd.DataFrame, file_path: Path) -> pd.Series:
        raw_time = df[TIME_COL].astype(str).str.strip()

        parsed_time = pd.to_datetime(
            raw_time,
            format=TIME_FORMAT,
            errors="coerce",
        )

        invalid_mask = parsed_time.isna()
        if invalid_mask.any():
            invalid_rows = invalid_mask[invalid_mask].index.tolist()
            preview_rows = invalid_rows[:10]
            raise ValueError(
                f"segment 文件存在无法解析的 {TIME_COL}: "
                f"file={file_path.name}, rows={preview_rows}"
            )

        return pd.Series(parsed_time, index=df.index, name=TIME_COL)

    def _check_strict_one_second_continuity(self, parsed_time: pd.Series) -> bool:
        if len(parsed_time) <= 1:
            return True

        deltas = parsed_time.diff().dropna()
        return bool((deltas == pd.Timedelta(seconds=1)).all())