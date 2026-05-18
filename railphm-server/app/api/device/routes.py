from flask import Blueprint, request
from app.core.auth import require_roles
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
    page = request.args.get('page', 1)
    size = request.args.get('size', 10)
    device_id = request.args.get('device_id')
    device_code = request.args.get('device_code', default='', type=str).strip() or None
    device_name = request.args.get('device_name', default='', type=str).strip() or None
    device_type = request.args.get('device_type', default='', type=str).strip() or None
    car_no = request.args.get('car_no', default='', type=str).strip() or None
    atp_type = request.args.get('atp_type', default='', type=str).strip() or None
    train_no = request.args.get('train_no', default='', type=str).strip() or None
    attach_bureau = request.args.get('attach_bureau', default='', type=str).strip() or None
    device_status = request.args.get('device_status')

    data = DeviceService.get_device_list(
        page=page,
        size=size,
        device_id=device_id,
        device_code=device_code,
        device_name=device_name,
        device_type=device_type,
        car_no=car_no,
        atp_type=atp_type,
        train_no=train_no,
        attach_bureau=attach_bureau,
        device_status=device_status
    )
    return success_response(data=data)

@device_bp.route('', methods=['POST'])
@require_roles("ADMIN")
def create_device():
    """
    新增设备台账
    """
    payload = request.get_json(silent=True)
    data = DeviceService.create_device(payload)
    return success_response(data=data)

@device_bp.route('/<int:device_id>', methods=['GET'])
def get_device(device_id):
    """
    获取单个设备详情
    """
    data = DeviceService.get_device_detail(device_id=device_id)
    return success_response(data=data)

@device_bp.route('/<int:device_id>', methods=['PUT'])
@require_roles("ADMIN")
def update_device(device_id):
    """
    编辑设备台账
    """
    payload = request.get_json(silent=True)
    data = DeviceService.update_device(device_id=device_id, payload=payload)
    return success_response(data=data)
