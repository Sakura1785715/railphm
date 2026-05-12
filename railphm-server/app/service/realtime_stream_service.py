from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict

from flask import current_app, has_app_context

from app.core.errors import BusinessException
from app.service.prediction_service import PredictionService


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class RealtimeStreamState:
    stream_id: str = "default"
    running: bool = False
    device_id: str = "ATP001"
    start_sample_index: int = 0
    current_sample_index: int = 0
    end_sample_index: int | None = None
    step: int = 1
    window_minutes: int = 30
    mc_samples: int = 20
    auto_wrap: bool = False
    last_result: Dict[str, Any] | None = None


class RealtimeStreamService:
    """
    请求驱动式仿真数据流服务。
    当前状态保存在 Python 进程内，仅适合本地开发和演示；多进程部署时状态不共享。
    """

    def __init__(self, prediction_service: type[PredictionService] = PredictionService):
        self._prediction_service = prediction_service
        self._state = RealtimeStreamState()
        self._lock = Lock()
        self._initialized = False

    def start(self, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise BusinessException(code=400, message="请求体必须为 JSON 对象", status_code=400)

        defaults = self._default_config()
        start_sample_index = self._parse_non_negative_int(
            config.get("start_sample_index", defaults["start_sample_index"]),
            "start_sample_index",
        )
        end_sample_index = self._parse_optional_end_sample_index(
            config.get("end_sample_index", defaults["end_sample_index"]),
            start_sample_index,
        )

        with self._lock:
            self._state = RealtimeStreamState(
                stream_id=defaults["stream_id"],
                running=True,
                device_id=self._parse_device_id(
                    config.get("device_id", defaults["device_id"])
                ),
                start_sample_index=start_sample_index,
                current_sample_index=start_sample_index,
                end_sample_index=end_sample_index,
                step=self._parse_positive_int(
                    config.get("step", defaults["step"]),
                    "step",
                ),
                window_minutes=self._parse_positive_int(
                    config.get("window_minutes", defaults["window_minutes"]),
                    "window_minutes",
                ),
                mc_samples=self._parse_positive_int(
                    config.get("mc_samples", defaults["mc_samples"]),
                    "mc_samples",
                ),
                auto_wrap=self._parse_bool(
                    config.get("auto_wrap", defaults["auto_wrap"]),
                    "auto_wrap",
                ),
                last_result=None,
            )
            self._initialized = True
            return self._state_snapshot(include_last_result=False)

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._ensure_initialized()
            self._state.running = False
            return {
                "stream_id": self._state.stream_id,
                "running": self._state.running,
                "current_sample_index": self._state.current_sample_index,
            }

    def reset(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise BusinessException(code=400, message="请求体必须为 JSON 对象", status_code=400)

        with self._lock:
            self._ensure_initialized()
            sample_index = payload.get("sample_index")
            if sample_index is None or sample_index == "":
                reset_index = self._state.start_sample_index
            else:
                reset_index = self._parse_non_negative_int(sample_index, "sample_index")

            self._state.current_sample_index = reset_index
            self._state.running = False
            self._state.last_result = None

            return {
                "stream_id": self._state.stream_id,
                "running": self._state.running,
                "current_sample_index": self._state.current_sample_index,
            }

    def state(self) -> Dict[str, Any]:
        with self._lock:
            self._ensure_initialized()
            return self._state_snapshot(include_last_result=True)

    def next(self) -> Dict[str, Any]:
        with self._lock:
            self._ensure_initialized()
            if not self._state.running:
                raise BusinessException(code=400, message="仿真数据流未启动", status_code=400)

            sample_index = self._state.current_sample_index
            request_data = {
                "device_id": self._state.device_id,
                "ts_end": self._generate_ts_end(sample_index),
                "window_minutes": self._state.window_minutes,
                "sample_index": sample_index,
                "mc_samples": self._state.mc_samples,
            }

            prediction_result = self._prediction_service.infer_prediction(request_data)
            next_sample_index = sample_index + self._state.step
            self._update_after_success(next_sample_index)

            self._state.last_result = self._build_last_result(
                sample_index,
                prediction_result,
            )

            realtime_result = {
                **prediction_result,
                "stream_id": self._state.stream_id,
                "sample_index": sample_index,
                "next_sample_index": self._state.current_sample_index,
                "stream_state": {
                    "running": self._state.running,
                    "current_sample_index": self._state.current_sample_index,
                    "end_sample_index": self._state.end_sample_index,
                    "auto_wrap": self._state.auto_wrap,
                },
            }
            return realtime_result

    def reset_for_tests(self) -> None:
        with self._lock:
            self._state = RealtimeStreamState()
            self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        defaults = self._default_config()
        self._state = RealtimeStreamState(
            stream_id=defaults["stream_id"],
            running=False,
            device_id=defaults["device_id"],
            start_sample_index=defaults["start_sample_index"],
            current_sample_index=defaults["start_sample_index"],
            end_sample_index=defaults["end_sample_index"],
            step=defaults["step"],
            window_minutes=defaults["window_minutes"],
            mc_samples=defaults["mc_samples"],
            auto_wrap=defaults["auto_wrap"],
            last_result=None,
        )
        self._initialized = True

    def _default_config(self) -> Dict[str, Any]:
        config = current_app.config if has_app_context() else {}
        return {
            "stream_id": config.get("REALTIME_STREAM_ID", "default"),
            "device_id": config.get("REALTIME_DEFAULT_DEVICE_ID", "ATP001"),
            "start_sample_index": config.get("REALTIME_DEFAULT_START_SAMPLE_INDEX", 0),
            "end_sample_index": config.get("REALTIME_DEFAULT_END_SAMPLE_INDEX"),
            "step": config.get("REALTIME_DEFAULT_STEP", 1),
            "window_minutes": config.get("REALTIME_DEFAULT_WINDOW_MINUTES", 30),
            "mc_samples": config.get("REALTIME_DEFAULT_MC_SAMPLES", 20),
            "auto_wrap": config.get("REALTIME_DEFAULT_AUTO_WRAP", False),
            "ts_start": config.get("REALTIME_DEFAULT_TS_START", "2026-05-01 10:00:00"),
            "ts_step_seconds": config.get("REALTIME_TS_STEP_SECONDS", 1),
        }

    def _state_snapshot(self, include_last_result: bool) -> Dict[str, Any]:
        data = {
            "stream_id": self._state.stream_id,
            "running": self._state.running,
            "device_id": self._state.device_id,
            "start_sample_index": self._state.start_sample_index,
            "current_sample_index": self._state.current_sample_index,
            "end_sample_index": self._state.end_sample_index,
            "step": self._state.step,
            "window_minutes": self._state.window_minutes,
            "mc_samples": self._state.mc_samples,
            "auto_wrap": self._state.auto_wrap,
        }
        if include_last_result:
            data["last_result"] = self._state.last_result
        return data

    def _generate_ts_end(self, sample_index: int) -> str:
        defaults = self._default_config()
        try:
            start_dt = datetime.strptime(defaults["ts_start"], DATETIME_FORMAT)
        except ValueError as exc:
            raise BusinessException(
                code=500,
                message="实时流默认起始时间配置非法",
                status_code=500,
            ) from exc

        offset_seconds = sample_index * int(defaults["ts_step_seconds"])
        return (start_dt + timedelta(seconds=offset_seconds)).strftime(DATETIME_FORMAT)

    def _update_after_success(self, next_sample_index: int) -> None:
        end_sample_index = self._state.end_sample_index
        if end_sample_index is None or next_sample_index <= end_sample_index:
            self._state.current_sample_index = next_sample_index
            return

        if self._state.auto_wrap:
            self._state.current_sample_index = self._state.start_sample_index
            return

        self._state.current_sample_index = next_sample_index
        self._state.running = False

    def _build_last_result(
        self,
        sample_index: int,
        prediction_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "sample_index": sample_index,
            "risk_score": prediction_result.get("risk_score"),
            "health_score": prediction_result.get("health_score"),
            "alert_level": prediction_result.get("alert_level"),
        }

    def _parse_device_id(self, value: Any) -> str:
        if value is None or not isinstance(value, str) or not value.strip():
            raise BusinessException(code=400, message="device_id 必须为非空字符串", status_code=400)
        return value.strip()

    def _parse_positive_int(self, value: Any, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        if value <= 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为正整数", status_code=400)
        return value

    def _parse_non_negative_int(self, value: Any, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise BusinessException(code=400, message=f"{field_name} 必须为非负整数", status_code=400)
        if value < 0:
            raise BusinessException(code=400, message=f"{field_name} 必须为非负整数", status_code=400)
        return value

    def _parse_optional_end_sample_index(
        self,
        value: Any,
        start_sample_index: int,
    ) -> int | None:
        if value is None or value == "":
            return None
        end_sample_index = self._parse_non_negative_int(value, "end_sample_index")
        if end_sample_index < start_sample_index:
            raise BusinessException(
                code=400,
                message="end_sample_index 必须大于等于 start_sample_index",
                status_code=400,
            )
        return end_sample_index

    def _parse_bool(self, value: Any, field_name: str) -> bool:
        if not isinstance(value, bool):
            raise BusinessException(code=400, message=f"{field_name} 必须为布尔值", status_code=400)
        return value
