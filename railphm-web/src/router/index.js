import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import DeviceDetailView from '../views/DeviceDetailView.vue'
import DeviceLedgerView from '../views/DeviceLedgerView.vue'
import HealthCheckView from '../views/HealthCheckView.vue'
import ModulePlaceholderView from '../views/ModulePlaceholderView.vue'
import NotFoundView from '../views/NotFoundView.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: DashboardView,
    meta: {
      title: '系统首页'
    }
  },
  {
    path: '/health',
    name: 'health-check',
    component: HealthCheckView,
    meta: {
      title: '系统联通测试'
    }
  },
  {
    path: '/devices',
    name: 'devices',
    component: DeviceLedgerView,
    meta: {
      title: '设备台账',
      description: '查看设备基础档案信息，并支持最小范围筛选与详情跳转。'
    }
  },
  {
    path: '/devices/:id',
    name: 'device-detail',
    component: DeviceDetailView,
    meta: {
      title: '设备详情'
    }
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: ModulePlaceholderView,
    meta: {
      title: '运行监测',
      description: '后续将在这里接入历史监测曲线、关键指标查询与运行状态监测能力。'
    }
  },
  {
    path: '/predictions',
    name: 'predictions',
    component: ModulePlaceholderView,
    meta: {
      title: '风险预测',
      description: '后续将在这里接入风险趋势、模型输出结果和预测分析页面。'
    }
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: ModulePlaceholderView,
    meta: {
      title: '告警中心',
      description: '后续将在这里接入告警列表、告警详情和告警处理流程。'
    }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView,
    meta: {
      title: '页面不存在'
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.afterEach((to) => {
  const pageTitle = to.meta?.title ? `${to.meta.title} - RailPHM` : 'RailPHM'
  document.title = pageTitle
})

export default router
