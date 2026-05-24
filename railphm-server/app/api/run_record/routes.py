from flask import Blueprint, request

from app.core.response import success_response
from app.service.run_record_service import RunRecordService


run_record_bp = Blueprint("run_record", __name__)


@run_record_bp.route("", methods=["GET"])
def list_run_records():
    data = RunRecordService.list_records(
        page=request.args.get("page", 1),
        page_size=request.args.get("page_size", 10),
        device_code=request.args.get("device_code", default="", type=str).strip() or None,
        status=request.args.get("status", default="", type=str).strip() or None,
        has_alarm_label=request.args.get("has_alarm_label"),
        min_risk_score=request.args.get("min_risk_score"),
    )
    return success_response(data=data)


@run_record_bp.route("/random", methods=["GET"])
def get_random_run_record():
    data = RunRecordService.get_random(
        device_code=request.args.get("device_code", default="", type=str).strip() or None,
    )
    return success_response(data=data)


@run_record_bp.route("/<int:run_record_id>", methods=["GET"])
def get_run_record_detail(run_record_id: int):
    data = RunRecordService.get_detail(run_record_id)
    return success_response(data=data)


@run_record_bp.route("/<int:run_record_id>/monitor", methods=["GET"])
def get_run_record_monitor(run_record_id: int):
    data = RunRecordService.get_monitor_history(
        run_record_id=run_record_id,
        limit_value=request.args.get("limit"),
    )
    return success_response(data=data)


@run_record_bp.route("/<int:run_record_id>/infer", methods=["POST"])
def infer_run_record(run_record_id: int):
    data = RunRecordService.infer_record(
        run_record_id=run_record_id,
        payload=request.get_json(silent=True) or {},
    )
    return success_response(data=data)


@run_record_bp.route("/<int:run_record_id>/alert", methods=["POST"])
def generate_run_record_alert(run_record_id: int):
    data = RunRecordService.generate_record_alert(
        run_record_id=run_record_id,
        payload=request.get_json(silent=True) or {},
    )
    return success_response(data=data)
