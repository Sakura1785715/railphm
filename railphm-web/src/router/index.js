import { createRouter, createWebHistory } from 'vue-router'
import AlertCenterView from '../views/AlertCenterView.vue'
import DashboardView from '../views/DashboardView.vue'
import DeviceDetailView from '../views/DeviceDetailView.vue'
import DeviceLedgerView from '../views/DeviceLedgerView.vue'
import HealthCheckView from '../views/HealthCheckView.vue'
import LoginView from '../views/LoginView.vue'
import NotFoundView from '../views/NotFoundView.vue'
import RunRecordDetailView from '../views/RunRecordDetailView.vue'
import RunRecordView from '../views/RunRecordView.vue'
import { isLoggedIn } from '../utils/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: {
      title: '登录',
      public: true
    }
  },
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
    redirect: { name: 'run-records' }
  },
  {
    path: '/run-records',
    name: 'run-records',
    component: RunRecordView,
    meta: {
      title: '运行记录',
      description: '从测试片段池中选择连续运行记录，进行监测回放、风险预测与告警分析。'
    }
  },
  {
    path: '/run-records/:id',
    name: 'run-record-detail',
    component: RunRecordDetailView,
    meta: {
      title: '运行记录详情'
    }
  },
  {
    path: '/predictions',
    name: 'predictions',
    redirect: { name: 'run-records' }
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

router.beforeEach((to) => {
  const loggedIn = isLoggedIn()
  const isPublic = Boolean(to.meta?.public)

  if (loggedIn && to.name === 'login') {
    return {
      name: 'home'
    }
  }

  if (!loggedIn && !isPublic) {
    return {
      name: 'login',
      query: {
        redirect: to.fullPath
      }
    }
  }

  return true
})

router.afterEach((to) => {
  const pageTitle = to.meta?.title ? `${to.meta.title} - RailPHM` : 'RailPHM'
  document.title = pageTitle
})

export default router
