from flask import Blueprint, request
from app.core.response import success_response
from app.service.device_service import DeviceService

# 定义为 /api/v1/devices
device_bp = Blueprint('device', __name__)

@device_bp.route('', methods=['GET'])
def get_devices():
    """
    获取设备列表
    支持分页与最小筛选查询，默认 page=1, size=10
    """
    page = request.args.get('page', 1, type=int)
    size = request.args.get('size', 10, type=int)
    device_id = request.args.get('device_id', default=None, type=int)
    car_no = request.args.get('car_no', default='', type=str).strip() or None
    device_status = request.args.get('device_status', default=None, type=int)

    data = DeviceService.get_device_list(
        page=page,
        size=size,
        device_id=device_id,
        car_no=car_no,
        device_status=device_status
    )
    return success_response(data=data)

@device_bp.route('/<int:device_id>', methods=['GET'])
def get_device(device_id):
    """
    获取单个设备详情
    """
    data = DeviceService.get_device_detail(device_id=device_id)
    return success_response(data=data)
