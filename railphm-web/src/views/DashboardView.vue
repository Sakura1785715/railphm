<template>
  <section class="dashboard-page">
    <div class="page-card dashboard-hero">
      <div class="page-heading">
        <p class="page-tag">系统首页</p>
        <h2>RailPHM 运行总览</h2>
        <p class="page-description">
          展示系统当前服务状态、设备与告警概况，以及默认设备的最新风险结果，
          作为后续设备管理、运行监测、风险预测和告警中心模块的统一入口。
        </p>
      </div>

      <div class="action-bar">
        <button class="primary-button" type="button" @click="loadDashboard" :disabled="isRefreshing">
          {{ isRefreshing ? '刷新中...' : '刷新首页数据' }}
        </button>
        <RouterLink to="/health" class="secondary-link">查看系统联通测试</RouterLink>
      </div>
    </div>

    <section class="metric-grid">
      <MetricCard
        title="服务状态"
        :value="serviceMetric.value"
        :description="serviceMetric.description"
        :badge="serviceMetric.badge"
        :badge-tone="serviceMetric.badgeTone"
        :loading="serviceMetric.loading"
        :error="serviceMetric.error"
      />
      <MetricCard
        title="设备总数"
        :value="deviceMetric.value"
        :description="deviceMetric.description"
        :badge="deviceMetric.badge"
        :badge-tone="deviceMetric.badgeTone"
        :loading="deviceMetric.loading"
        :error="deviceMetric.error"
      />
      <MetricCard
        title="告警数量"
        :value="alertMetric.value"
        :description="alertMetric.description"
        :badge="alertMetric.badge"
        :badge-tone="alertMetric.badgeTone"
        :loading="alertMetric.loading"
        :error="alertMetric.error"
      />
    </section>

    <section class="dashboard-content-grid">
      <article class="page-card dashboard-section">
        <div class="dashboard-section__header">
          <div>
            <p class="page-tag">默认观测对象</p>
            <h3>最新风险结果</h3>
          </div>
          <span class="status-pill status-pill--muted">
            设备 ID {{ DEFAULT_DASHBOARD_DEVICE_ID }}
          </span>
        </div>

        <p class="section-description">
          当前阶段首页默认展示设备 {{ DEFAULT_DASHBOARD_DEVICE_ID }} 的最新一次风险分析结果，接口来自
          <code>/api/v1/predictions/latest</code>。
        </p>

        <div v-if="predictionState.loading" class="state-panel loading-state">
          正在获取默认设备的最新风险结果...
        </div>

        <div v-else-if="predictionState.error" class="state-panel error-state">
          <h3>风险结果加载失败</h3>
          <p>{{ predictionState.error }}</p>
          <p class="subtle-text">首页其他区域仍可继续使用，你可以稍后重新刷新数据。</p>
        </div>

        <div v-else-if="!predictionState.data" class="state-panel empty-state">
          当前默认设备暂无最新风险结果，请在后端补充 mock 数据或后续接入真实结果后再查看。
        </div>

        <div v-else class="result-panel result-panel--compact">
          <div class="result-panel__headline">
            <div>
              <p class="result-panel__eyebrow">观测设备</p>
              <h4>{{ defaultDeviceTitle }}</h4>
            </div>
            <span :class="['status-pill', riskStatusClass]">{{ riskStatusText }}</span>
          </div>

          <dl class="dashboard-data-list">
            <div>
              <dt>设备编号</dt>
              <dd>{{ predictionState.data.device_id }}</dd>
            </div>
            <div>
              <dt>车号</dt>
              <dd>{{ defaultDeviceCarNo }}</dd>
            </div>
            <div>
              <dt>风险分数</dt>
              <dd>{{ formatDecimal(predictionState.data.risk_score) }}</dd>
            </div>
            <div>
              <dt>风险波动</dt>
              <dd>{{ formatDecimal(predictionState.data.risk_std) }}</dd>
            </div>
            <div>
              <dt>健康度</dt>
              <dd>{{ formatDecimal(predictionState.data.health_score) }}</dd>
            </div>
            <div>
              <dt>模型版本</dt>
              <dd>{{ predictionState.data.model_version || '未返回' }}</dd>
            </div>
            <div>
              <dt>时间窗口</dt>
              <dd>{{ predictionState.data.window_start_time }} ~ {{ predictionState.data.window_end_time }}</dd>
            </div>
          </dl>

          <p v-if="defaultDeviceError" class="subtle-text">
            设备详情补充信息加载失败：{{ defaultDeviceError }}
          </p>
        </div>
      </article>

      <article class="page-card dashboard-section">
        <div class="dashboard-section__header">
          <div>
            <p class="page-tag">模块导航</p>
            <h3>快速跳转入口</h3>
          </div>
        </div>

        <p class="section-description">
          以下入口用于后续模块扩展。当前未完成的页面会进入明确的占位页，不会出现空白或死链接。
        </p>

        <div class="quick-link-grid">
          <QuickLinkCard
            v-for="item in DASHBOARD_QUICK_LINKS"
            :key="item.to"
            :item="item"
          />
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import MetricCard from '../components/dashboard/MetricCard.vue'
import QuickLinkCard from '../components/dashboard/QuickLinkCard.vue'
import { getAlertList } from '../api/alert'
import { getDeviceDetail, getDeviceList } from '../api/device'
import { getHealthStatus } from '../api/health'
import { getLatestPrediction } from '../api/prediction'
import {
  DASHBOARD_ALERT_LIST_PARAMS,
  DASHBOARD_DEVICE_LIST_PARAMS,
  DASHBOARD_QUICK_LINKS,
  DEFAULT_DASHBOARD_DEVICE_ID
} from '../constants/dashboard'

const serviceMetric = ref(createMetricState())
const deviceMetric = ref(createMetricState())
const alertMetric = ref(createMetricState())
const predictionState = ref({
  loading: true,
  error: '',
  data: null
})
const defaultDevice = ref(null)
const defaultDeviceError = ref('')

function createMetricState() {
  return {
    loading: true,
    error: '',
    value: '--',
    description: '',
    badge: '',
    badgeTone: 'default'
  }
}

const isRefreshing = computed(
  () => serviceMetric.value.loading || deviceMetric.value.loading || alertMetric.value.loading || predictionState.value.loading
)

const defaultDeviceTitle = computed(() => {
  if (!defaultDevice.value) {
    return `默认设备 ${DEFAULT_DASHBOARD_DEVICE_ID}`
  }

  return `${defaultDevice.value.car_no} / 设备 ${defaultDevice.value.device_id}`
})

const defaultDeviceCarNo = computed(() => defaultDevice.value?.car_no || '暂无设备详情')

const riskStatusText = computed(() => {
  const score = predictionState.value.data?.health_score

  if (typeof score !== 'number') {
    return '结果已更新'
  }

  if (score <= 30) {
    return '高风险'
  }

  if (score <= 70) {
    return '需关注'
  }

  return '状态良好'
})

const riskStatusClass = computed(() => {
  const score = predictionState.value.data?.health_score

  if (typeof score !== 'number') {
    return 'status-pill--muted'
  }

  if (score <= 30) {
    return 'status-pill--danger'
  }

  if (score <= 70) {
    return 'status-pill--warning'
  }

  return 'status-pill--success'
})

function formatDecimal(value) {
  return typeof value === 'number' ? value.toFixed(2) : '未返回'
}

async function loadDashboard() {
  serviceMetric.value = createMetricState()
  deviceMetric.value = createMetricState()
  alertMetric.value = createMetricState()
  predictionState.value = {
    loading: true,
    error: '',
    data: null
  }
  defaultDeviceError.value = ''

  const [healthResult, deviceListResult, alertListResult, latestPredictionResult, deviceDetailResult] =
    await Promise.allSettled([
      getHealthStatus(),
      getDeviceList(DASHBOARD_DEVICE_LIST_PARAMS),
      getAlertList(DASHBOARD_ALERT_LIST_PARAMS),
      getLatestPrediction(DEFAULT_DASHBOARD_DEVICE_ID),
      getDeviceDetail(DEFAULT_DASHBOARD_DEVICE_ID)
    ])

  if (healthResult.status === 'fulfilled') {
    const payload = healthResult.value.data || {}
    serviceMetric.value = {
      loading: false,
      error: '',
      value: payload.status === 'running' ? '正常' : payload.status || '未知',
      description: `${payload.service || '未知服务'} · 版本 ${payload.version || '未返回'}`,
      badge: payload.status === 'running' ? '已联通' : '待确认',
      badgeTone: payload.status === 'running' ? 'success' : 'warning'
    }
  } else {
    serviceMetric.value = {
      loading: false,
      error: healthResult.reason?.message || '服务状态获取失败',
      value: '--',
      description: '',
      badge: '',
      badgeTone: 'default'
    }
  }

  if (deviceListResult.status === 'fulfilled') {
    const payload = deviceListResult.value.data || {}
    const items = Array.isArray(payload.items) ? payload.items : []

    deviceMetric.value = {
      loading: false,
      error: '',
      value: payload.total ?? items.length,
      description: '来自设备列表接口的当前台账总量',
      badge: '台账',
      badgeTone: 'default'
    }

    if (!defaultDevice.value) {
      defaultDevice.value = items.find((item) => item.device_id === DEFAULT_DASHBOARD_DEVICE_ID) || null
    }
  } else {
    deviceMetric.value = {
      loading: false,
      error: deviceListResult.reason?.message || '设备总数获取失败',
      value: '--',
      description: '',
      badge: '',
      badgeTone: 'default'
    }
  }

  if (alertListResult.status === 'fulfilled') {
    const payload = alertListResult.value.data || {}

    alertMetric.value = {
      loading: false,
      error: '',
      value: payload.total ?? 0,
      description: '来自告警列表接口的当前总量',
      badge: '总量',
      badgeTone: (payload.total ?? 0) > 0 ? 'warning' : 'success'
    }
  } else {
    alertMetric.value = {
      loading: false,
      error: alertListResult.reason?.message || '告警数量获取失败',
      value: '--',
      description: '',
      badge: '',
      badgeTone: 'default'
    }
  }

  if (latestPredictionResult.status === 'fulfilled') {
    predictionState.value = {
      loading: false,
      error: '',
      data: latestPredictionResult.value.data || null
    }
  } else {
    predictionState.value = {
      loading: false,
      error: latestPredictionResult.reason?.message || '最新风险结果获取失败',
      data: null
    }
  }

  if (deviceDetailResult.status === 'fulfilled') {
    defaultDevice.value = deviceDetailResult.value.data || defaultDevice.value
  } else if (!defaultDevice.value) {
    defaultDeviceError.value = deviceDetailResult.reason?.message || '默认设备详情获取失败'
  } else {
    defaultDeviceError.value = deviceDetailResult.reason?.message || '默认设备详情获取失败'
  }
}

onMounted(() => {
  loadDashboard()
})
</script>
