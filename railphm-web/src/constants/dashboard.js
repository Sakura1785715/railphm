// 当前首页默认观测设备。
// 统一集中在此处管理，避免在页面模板和请求逻辑中散落魔法值。
export const DEFAULT_DASHBOARD_DEVICE_ID = 1

export const DASHBOARD_DEVICE_LIST_PARAMS = {
  page: 1,
  size: 100
}

export const DASHBOARD_ALERT_LIST_PARAMS = {
  page: 1,
  size: 1
}

export const LAYOUT_NAV_ITEMS = [
  {
    title: '系统首页',
    description: '系统运行总览与默认设备风险概况',
    to: '/',
    icon: 'home'
  },
  {
    title: '设备台账',
    description: '设备主数据与台账入口',
    to: '/devices',
    icon: 'device'
  },
  {
    title: '运行监测',
    description: '监测序列与运行状态入口',
    to: '/monitor',
    icon: 'monitor'
  },
  {
    title: '风险预测',
    description: '模型结果与风险评估入口',
    to: '/predictions',
    icon: 'prediction'
  },
  {
    title: '告警中心',
    description: '告警记录与处理入口',
    to: '/alerts',
    icon: 'alert'
  }
]

export const LAYOUT_SUPPORT_ITEMS = [
  {
    title: '系统联通测试',
    description: '验证前后端健康接口联通情况',
    to: '/health',
    icon: 'health'
  }
]

export const DASHBOARD_QUICK_LINKS = [
  {
    title: '设备台账',
    description: '查看设备主数据、车组编号与基础设备状态。',
    to: '/devices',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'device'
  },
  {
    title: '运行监测',
    description: '查看监测序列、运行状态与后续时序分析入口。',
    to: '/monitor',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'monitor'
  },
  {
    title: '风险预测',
    description: '查看风险评估结果与模型输出相关业务页面。',
    to: '/predictions',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'prediction'
  },
  {
    title: '告警中心',
    description: '查看系统告警记录、级别状态与处理入口。',
    to: '/alerts',
    statusText: '模块入口',
    actionText: '查看模块',
    icon: 'alert'
  }
]
