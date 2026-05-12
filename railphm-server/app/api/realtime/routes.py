from flask import Blueprint, request

from app.core.response import success_response
from app.service.realtime_stream_service import RealtimeStreamService


realtime_bp = Blueprint("realtime", __name__)
realtime_stream_service = RealtimeStreamService()
_INVALID_JSON_BODY = object()


def _read_optional_json_body():
    payload = request.get_json(silent=True)
    if payload is None and request.data:
        return _INVALID_JSON_BODY
    return payload or {}


@realtime_bp.route("/start", methods=["POST"])
def start_realtime_stream():
    data = realtime_stream_service.start(_read_optional_json_body())
    return success_response(data=data)


@realtime_bp.route("/stop", methods=["POST"])
def stop_realtime_stream():
    data = realtime_stream_service.stop()
    return success_response(data=data)


@realtime_bp.route("/reset", methods=["POST"])
def reset_realtime_stream():
    data = realtime_stream_service.reset(_read_optional_json_body())
    return success_response(data=data)


@realtime_bp.route("/state", methods=["GET"])
def get_realtime_stream_state():
    data = realtime_stream_service.state()
    return success_response(data=data)


@realtime_bp.route("/next", methods=["GET"])
def next_realtime_prediction():
    data = realtime_stream_service.next()
    return success_response(data=data)
