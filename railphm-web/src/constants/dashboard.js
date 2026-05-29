// 当前首页默认观测设备。
// 统一集中在此处管理，避免在页面模板和请求逻辑中散落魔法值。
export const DEFAULT_DASHBOARD_DEVICE_ID = 1

export const DASHBOARD_DEVICE_LIST_PARAMS = {
  page: 1,
  size: 100
}

export const DASHBOARD_ALERT_LIST_PARAMS = {
  page: 1,
  size: 20
}

export const DASHBOARD_PREDICTION_HISTORY_PARAMS = {
  device_id: DEFAULT_DASHBOARD_DEVICE_ID,
  start_time: '2026-04-01 00:00:00',
  end_time: '2026-04-02 23:59:59'
}

export const LAYOUT_NAV_ITEMS = [
  {
    title: '系统首页',
    description: '系统运行总览与默认设备风险概况',
    to: '/',
    icon: 'home',
    roles: ['OPS', 'ADMIN']
  },
  {
    title: '设备台账',
    description: '设备主数据与台账入口',
    to: '/devices',
    icon: 'device',
    roles: ['ADMIN']
  },
  {
    title: '运行监测',
    description: '监测序列与运行状态入口',
    to: '/monitor',
    icon: 'monitor',
    roles: ['OPS', 'ADMIN']
  },
  {
    title: '风险预测',
    description: '模型结果与风险评估入口',
    to: '/predictions',
    icon: 'prediction',
    roles: ['OPS', 'ADMIN']
  },
  {
    title: '告警中心',
    description: '告警记录与处理入口',
    to: '/alerts',
    icon: 'alert',
    roles: ['OPS', 'ADMIN']
  }
]

export const LAYOUT_SUPPORT_ITEMS = [
  {
    title: '系统联通测试',
    description: '验证前后端健康接口联通情况',
    to: '/health',
    icon: 'health',
    roles: []
  }
]

export const DASHBOARD_QUICK_LINKS = [
  {
    title: '设备台账',
    description: '查看和管理设备基本信息与台账。',
    to: '/devices',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'device'
  },
  {
    title: '运行记录',
    description: '查看设备运行与状态变更记录。',
    to: '/run-records',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'service'
  },
  {
    title: '告警中心',
    description: '查看、处理和跟踪告警事件。',
    to: '/alerts',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'alert'
  },
  {
    title: '系统联通测试',
    description: '验证系统与设备联通状态。',
    to: '/health',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'health'
  }
]
