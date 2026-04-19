export const DEFAULT_DASHBOARD_DEVICE_ID = 1

export const DASHBOARD_DEVICE_LIST_PARAMS = {
  page: 1,
  size: 100
}

export const DASHBOARD_ALERT_LIST_PARAMS = {
  page: 1,
  size: 1
}

export const DASHBOARD_QUICK_LINKS = [
  {
    title: '设备管理',
    description: '查看设备台账、基础状态与后续详情能力入口。',
    to: '/devices',
    statusText: '待建设',
    actionText: '进入设备页'
  },
  {
    title: '运行监测',
    description: '预留历史监测曲线与运行监测数据展示入口。',
    to: '/monitor',
    statusText: '待建设',
    actionText: '进入监测页'
  },
  {
    title: '风险预测',
    description: '预留风险趋势、模型输出与推理结果展示入口。',
    to: '/predictions',
    statusText: '待建设',
    actionText: '进入预测页'
  },
  {
    title: '告警中心',
    description: '预留告警列表、处理记录与告警详情入口。',
    to: '/alerts',
    statusText: '待建设',
    actionText: '进入告警页'
  }
]
