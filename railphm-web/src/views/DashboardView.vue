<template>
  <section class="dashboard-page">
    <div class="dashboard-topbar">
      <div class="dashboard-topbar__content">
        <p class="page-tag">系统首页</p>
        <h2>运行总览</h2>
        <p class="page-description">
          展示系统服务状态、设备概况、默认设备风险结果与业务入口，首页核心聚焦默认设备的最新健康评估。
        </p>
      </div>

      <div class="dashboard-topbar__meta">
        <span :class="['status-pill', `status-pill--${systemStatus.tone}`]">{{ systemStatus.label }}</span>
        <span class="dashboard-topbar__timestamp">最近更新 {{ lastUpdatedText }}</span>
        <button class="secondary-button" type="button" @click="loadDashboard" :disabled="isRefreshing">
          {{ isRefreshing ? '更新中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <section class="metric-grid">
      <MetricCard
        eyebrow="服务健康"
        title="系统服务状态"
        :value="serviceMetric.value"
        :description="serviceMetric.description"
        :helper="serviceMetric.helper"
        :badge="serviceMetric.badge"
        :badge-tone="serviceMetric.badgeTone"
        :loading="serviceMetric.loading"
        :error="serviceMetric.error"
        :tone="serviceMetric.tone"
        icon="service"
        :icon-tone="serviceMetric.iconTone"
      />
      <MetricCard
        eyebrow="设备概况"
        title="设备总数"
        :value="deviceMetric.value"
        :description="deviceMetric.description"
        :helper="deviceMetric.helper"
        :badge="deviceMetric.badge"
        :badge-tone="deviceMetric.badgeTone"
        :loading="deviceMetric.loading"
        :error="deviceMetric.error"
        :tone="deviceMetric.tone"
        icon="device"
        :icon-tone="deviceMetric.iconTone"
      />
      <MetricCard
        eyebrow="告警态势"
        title="告警数量"
        :value="alertMetric.value"
        :description="alertMetric.description"
        :helper="alertMetric.helper"
        :badge="alertMetric.badge"
        :badge-tone="alertMetric.badgeTone"
        :loading="alertMetric.loading"
        :error="alertMetric.error"
        :tone="alertMetric.tone"
        icon="alert"
        :icon-tone="alertMetric.iconTone"
      />
      <MetricCard
        eyebrow="默认设备"
        title="默认设备健康概况"
        :value="predictionMetric.value"
        value-suffix="/ 100"
        :description="predictionMetric.description"
        :helper="predictionMetric.helper"
        :badge="predictionMetric.badge"
        :badge-tone="predictionMetric.badgeTone"
        :loading="predictionMetric.loading"
        :error="predictionMetric.error"
        :tone="predictionMetric.tone"
        icon="risk"
        :icon-tone="predictionMetric.iconTone"
        emphasis
      />
    </section>

    <section class="dashboard-content-grid">
      <RiskSummaryCard
        :loading="predictionState.loading"
        :error="predictionState.error"
        :prediction="predictionState.data"
        :device="defaultDevice"
        :device-error="defaultDeviceError"
        :default-device-id="DEFAULT_DASHBOARD_DEVICE_ID"
        @retry="loadDashboard"
      />

      <article class="quick-entry-panel">
        <div class="quick-entry-panel__header">
          <div>
            <p class="page-tag">业务入口</p>
            <h3>快速跳转入口</h3>
          </div>
          <span class="status-pill status-pill--muted">统一入口</span>
        </div>

        <p class="section-description">
          保留当前系统已存在的业务入口，未完成模块继续进入占位页，避免出现空白页或死链。
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

    <RiskDetailTable
      title="风险结果明细"
      description="展示当前默认设备最新风险结果的结构化字段信息，用于辅助查看模型输出与评估摘要。"
      :columns="detailColumns"
      :rows="detailRows"
      :loading="predictionState.loading"
      :error="predictionState.error"
      empty-text="当前默认设备暂无最新风险结果，待接口返回后将在此处自动补齐结构化明细。"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import MetricCard from '../components/dashboard/MetricCard.vue'
import QuickLinkCard from '../components/dashboard/QuickLinkCard.vue'
import RiskDetailTable from '../components/dashboard/RiskDetailTable.vue'
import RiskSummaryCard from '../components/dashboard/RiskSummaryCard.vue'
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
import {
  formatCount,
  formatDateTime,
  formatDecimal,
  formatModelVersion,
  getRiskLevelMeta,
  getServiceStatusMeta
} from '../utils/dashboard'

const serviceMetric = ref(createMetricState())
const deviceMetric = ref(createMetricState())
const alertMetric = ref(createMetricState())
const predictionMetric = ref(createMetricState())
const predictionState = ref({
  loading: true,
  error: '',
  data: null
})
const defaultDevice = ref(null)
const defaultDeviceError = ref('')
const lastLoadedAt = ref(null)

function createMetricState() {
  return {
    loading: true,
    error: '',
    value: '--',
    description: '',
    helper: '',
    badge: '',
    badgeTone: 'default',
    tone: 'default',
    iconTone: 'accent'
  }
}

const isRefreshing = computed(
  () =>
    serviceMetric.value.loading ||
    deviceMetric.value.loading ||
    alertMetric.value.loading ||
    predictionMetric.value.loading ||
    predictionState.value.loading
)

const systemStatus = computed(() => {
  if (serviceMetric.value.loading) {
    return {
      label: '系统状态获取中',
      tone: 'muted'
    }
  }

  if (serviceMetric.value.error) {
    return {
      label: '系统状态待确认',
      tone: 'warning'
    }
  }

  return {
    label: serviceMetric.value.value === '系统在线' ? '系统在线' : '状态待确认',
    tone: serviceMetric.value.value === '系统在线' ? 'success' : 'warning'
  }
})

const lastUpdatedText = computed(() => {
  if (!lastLoadedAt.value) {
    return '尚未更新'
  }

  return formatDateTime(lastLoadedAt.value)
})

// 首页底部明细表仅展示默认设备最新风险结果及其必要补充字段。
// 保持“结构化结果展示”语义，不引入筛选、操作列等新业务能力。
const detailColumns = [
  { key: 'device_id', title: '设备编号' },
  { key: 'car_no', title: '车组编号' },
  { key: 'risk_score', title: '风险分数' },
  { key: 'health_score', title: '健康度' },
  { key: 'risk_std', title: '风险波动' },
  { key: 'risk_level', title: '风险等级' },
  { key: 'model_version', title: '模型版本' },
  { key: 'window_start_time', title: '窗口开始时间' },
  { key: 'window_end_time', title: '窗口结束时间' },
  { key: 'updated_at', title: '最近更新时间' }
]

const detailRows = computed(() => {
  if (!predictionState.value.data) {
    return []
  }

  const riskLevelMeta = getRiskLevelMeta(predictionState.value.data.health_score)

  return [
    {
      device_id: String(predictionState.value.data.device_id ?? DEFAULT_DASHBOARD_DEVICE_ID),
      car_no: defaultDevice.value?.car_no || '未返回',
      risk_score: formatDecimal(predictionState.value.data.risk_score),
      health_score: formatDecimal(predictionState.value.data.health_score, 1),
      risk_std: formatDecimal(predictionState.value.data.risk_std),
      risk_level: riskLevelMeta.label,
      risk_levelTone: riskLevelMeta.tone,
      model_version: predictionState.value.data.model_version || '未返回',
      window_start_time: formatDateTime(predictionState.value.data.window_start_time),
      window_end_time: formatDateTime(predictionState.value.data.window_end_time),
      updated_at: formatDateTime(predictionState.value.data.window_end_time)
    }
  ]
})

async function loadDashboard() {
  serviceMetric.value = createMetricState()
  deviceMetric.value = createMetricState()
  alertMetric.value = createMetricState()
  predictionMetric.value = createMetricState()
  predictionState.value = {
    loading: true,
    error: '',
    data: null
  }
  defaultDeviceError.value = ''

  // 首页数据全部来自现有后端接口，不新增任何接口语义。
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
    const serviceMeta = getServiceStatusMeta(payload.status)

    serviceMetric.value = {
      loading: false,
      error: '',
      value: serviceMeta.label,
      description: `${payload.service || '未知服务'} · 版本 ${payload.version || '未返回'}`,
      helper: serviceMeta.description,
      badge: serviceMeta.badge,
      badgeTone: serviceMeta.tone,
      tone: serviceMeta.tone === 'warning' ? 'warning' : 'success',
      iconTone: serviceMeta.tone === 'warning' ? 'warning' : 'success'
    }
  } else {
    serviceMetric.value = {
      loading: false,
      error: healthResult.reason?.message || '服务状态加载失败',
      value: '--',
      description: '',
      helper: '',
      badge: '',
      badgeTone: 'default',
      tone: 'warning',
      iconTone: 'warning'
    }
  }

  if (deviceListResult.status === 'fulfilled') {
    const payload = deviceListResult.value.data || {}
    const items = Array.isArray(payload.items) ? payload.items : []

    deviceMetric.value = {
      loading: false,
      error: '',
      value: formatCount(payload.total ?? items.length),
      description: '来自设备台账的当前设备总量',
      helper: '数据来源：/api/v1/devices',
      badge: '设备台账',
      badgeTone: 'default',
      tone: 'default',
      iconTone: 'accent'
    }

    if (!defaultDevice.value) {
      defaultDevice.value = items.find((item) => item.device_id === DEFAULT_DASHBOARD_DEVICE_ID) || null
    }
  } else {
    deviceMetric.value = {
      loading: false,
      error: deviceListResult.reason?.message || '设备总数加载失败',
      value: '--',
      description: '',
      helper: '',
      badge: '',
      badgeTone: 'default',
      tone: 'warning',
      iconTone: 'warning'
    }
  }

  if (alertListResult.status === 'fulfilled') {
    const payload = alertListResult.value.data || {}
    const total = payload.total ?? 0

    alertMetric.value = {
      loading: false,
      error: '',
      value: formatCount(total),
      description: '当前系统告警记录总数',
      helper: '数据来源：/api/v1/alerts',
      badge: '告警记录',
      badgeTone: total > 0 ? 'warning' : 'success',
      tone: total > 0 ? 'warning' : 'default',
      iconTone: total > 0 ? 'warning' : 'accent'
    }
  } else {
    alertMetric.value = {
      loading: false,
      error: alertListResult.reason?.message || '告警数量加载失败',
      value: '--',
      description: '',
      helper: '',
      badge: '',
      badgeTone: 'default',
      tone: 'warning',
      iconTone: 'warning'
    }
  }

  if (latestPredictionResult.status === 'fulfilled') {
    const payload = latestPredictionResult.value.data || null
    const riskLevelMeta = getRiskLevelMeta(payload?.health_score)

    predictionState.value = {
      loading: false,
      error: '',
      data: payload
    }

    predictionMetric.value = {
      loading: false,
      error: '',
      value: payload ? formatDecimal(payload.health_score, 1) : '--',
      description: payload
        ? `设备 ${payload.device_id} · ${riskLevelMeta.label}`
        : '当前暂无默认设备风险结果',
      helper: payload
        ? `风险分数 ${formatDecimal(payload.risk_score)} · ${formatModelVersion(payload.model_version)}`
        : '数据来源：/api/v1/predictions/latest',
      badge: payload ? riskLevelMeta.label : '暂无结果',
      badgeTone: payload ? riskLevelMeta.tone : 'muted',
      tone: payload ? (riskLevelMeta.tone === 'muted' ? 'focus' : riskLevelMeta.tone) : 'default',
      iconTone: payload ? (riskLevelMeta.tone === 'muted' ? 'accent' : riskLevelMeta.tone) : 'accent'
    }
  } else {
    predictionState.value = {
      loading: false,
      error: latestPredictionResult.reason?.message || '风险结果加载失败',
      data: null
    }

    predictionMetric.value = {
      loading: false,
      error: latestPredictionResult.reason?.message || '风险结果加载失败',
      value: '--',
      description: '',
      helper: '',
      badge: '',
      badgeTone: 'default',
      tone: 'warning',
      iconTone: 'warning'
    }
  }

  if (deviceDetailResult.status === 'fulfilled') {
    defaultDevice.value = deviceDetailResult.value.data || defaultDevice.value
  } else {
    defaultDeviceError.value = deviceDetailResult.reason?.message || '默认设备详情加载失败'
  }

  lastLoadedAt.value = new Date()
}

onMounted(() => {
  loadDashboard()
})
</script>

<style scoped>
.dashboard-page {
  display: grid;
  gap: 22px;
}

.dashboard-topbar {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px;
  background: #ffffff;
  border: 1px solid #d7e1ee;
  border-radius: 22px;
  box-shadow: 0 20px 42px rgba(15, 23, 42, 0.05);
}

.dashboard-topbar__content {
  display: grid;
  gap: 10px;
}

.dashboard-topbar__meta {
  display: grid;
  justify-items: end;
  align-content: start;
  gap: 12px;
}

.dashboard-topbar__timestamp {
  color: #607189;
  font-size: 0.95rem;
}

.page-tag,
.page-description,
.section-description {
  margin: 0;
}

.page-tag {
  color: #0f6c85;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dashboard-topbar h2,
.quick-entry-panel h3 {
  margin: 0;
  color: #0f172a;
}

.page-description,
.section-description {
  max-width: 760px;
  color: #5b6d86;
  line-height: 1.7;
}

.metric-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-content-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.55fr) minmax(340px, 0.95fr);
  align-items: start;
}

.quick-entry-panel {
  display: grid;
  gap: 18px;
  padding: 26px;
  background: #ffffff;
  border: 1px solid #d7e1ee;
  border-radius: 22px;
  box-shadow: 0 20px 42px rgba(15, 23, 42, 0.05);
}

.quick-entry-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.quick-link-grid {
  display: grid;
  gap: 14px;
}

.secondary-button {
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid #cfe0eb;
  border-radius: 999px;
  background: #ffffff;
  color: #0f6c85;
  font-weight: 600;
  cursor: pointer;
}

.secondary-button:disabled {
  cursor: wait;
  opacity: 0.72;
}

@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard-topbar,
  .dashboard-topbar__meta,
  .quick-entry-panel__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .dashboard-topbar__meta {
    justify-items: start;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-topbar,
  .quick-entry-panel {
    padding: 22px;
  }
}
</style>
