import { createRouter, createWebHistory } from 'vue-router'
import AlertCenterView from '../views/AlertCenterView.vue'
import DashboardView from '../views/DashboardView.vue'
import DeviceDetailView from '../views/DeviceDetailView.vue'
import DeviceLedgerView from '../views/DeviceLedgerView.vue'
import HealthCheckView from '../views/HealthCheckView.vue'
import MonitorView from '../views/MonitorView.vue'
import NotFoundView from '../views/NotFoundView.vue'
import PredictionView from '../views/PredictionView.vue'

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
    component: MonitorView,
    meta: {
      title: '运行监测',
      description: '查询并展示 ATP 车载监测数据的时序变化。'
    }
  },
  {
    path: '/predictions',
    name: 'predictions',
    component: PredictionView,
    meta: {
      title: '风险预测',
      description: '展示设备最新风险结果、历史趋势和 mock 推理演示页面。'
    }
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: AlertCenterView,
    meta: {
      title: '告警中心',
      description: '集中展示系统告警记录，支持筛选、分页与详情查看。'
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
