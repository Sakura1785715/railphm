"""
接收前端请求，取出参数，然后把任务交给 RunRecordService
"""
from flask import Blueprint, request

from app.core.response import success_response
from app.service.run_record_service import RunRecordService

# 创建运行记录蓝图
run_record_bp = Blueprint("run_record", __name__)

# 查询运行记录列表接口
@run_record_bp.route("", methods=["GET"])
def list_run_records():
    data = RunRecordService.list_records(
        # 从URL中去参数，传给Service
        page=request.args.get("page", 1),
        page_size=request.args.get("page_size", 10),
        device_code=request.args.get("device_code", default="", type=str).strip() or None,
        status=request.args.get("status", default="", type=str).strip() or None,
        has_alarm_label=request.args.get("has_alarm_label"),
        min_risk_score=request.args.get("min_risk_score"),
    )
    return success_response(data=data)


# 随机获取运行记录接口
@run_record_bp.route("/random", methods=["GET"])
def get_random_run_record():
    data = RunRecordService.get_random(
        device_code=request.args.get("device_code", default="", type=str).strip() or None,
    )
    return success_response(data=data)


# 获取运行记录详情接口
@run_record_bp.route("/<int:run_record_id>", methods=["GET"])
def get_run_record_detail(run_record_id: int):
    data = RunRecordService.get_detail(run_record_id)
    return success_response(data=data)


# 获取运行记录监测数据接口
@run_record_bp.route("/<int:run_record_id>/monitor", methods=["GET"])
def get_run_record_monitor(run_record_id: int):
    data = RunRecordService.get_monitor_history(
        run_record_id=run_record_id,
        # 限制最多查多少条监测点
        limit_value=request.args.get("limit"), 
    )
    return success_response(data=data)

# 执行运行记录预测接口
@run_record_bp.route("/<int:run_record_id>/infer", methods=["POST"])
def infer_run_record(run_record_id: int):
    data = RunRecordService.infer_record(
        run_record_id=run_record_id,
        # 推理参数
        payload=request.get_json(silent=True) or {},
    )
    return success_response(data=data)

# 生成运行记录告警接口
@run_record_bp.route("/<int:run_record_id>/alert", methods=["POST"])
def generate_run_record_alert(run_record_id: int):
    data = RunRecordService.generate_record_alert(
        run_record_id=run_record_id,
        payload=request.get_json(silent=True) or {},
    )
    return success_response(data=data)
