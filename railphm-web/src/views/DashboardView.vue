<template>
  <section class="dashboard-page">
    <PageHeader
      title="系统首页"
      eyebrow="系统首页"
      description="面向 ATP 车载监测数据，集中展示设备运行状态、故障风险、健康度和告警处理情况。"
      :meta="headerMetaText"
    >
      <template #actions>
        <span :class="['status-pill', `status-pill--${systemStatus.tone}`]">{{ systemStatus.label }}</span>
        <span class="status-pill status-pill--default">{{ currentRoleText }}</span>
        <button class="secondary-button" type="button" :disabled="isRefreshing" @click="loadDashboard">
          {{ isRefreshing ? '刷新中...' : '刷新数据' }}
        </button>
      </template>
    </PageHeader>

    <section class="stat-grid dashboard-stat-grid">
      <StatCard
        v-for="item in overviewMetrics"
        :key="item.key"
        :label="item.label"
        :value="item.value"
        :unit="item.unit"
        :description="item.description"
        :trend="item.trend"
        :type="item.type"
        :loading="item.loading"
      >
        <template #extra>
          <p class="dashboard-card-hint" :class="{ 'dashboard-card-hint--error': item.error }">
            {{ item.helper }}
          </p>
        </template>
      </StatCard>
    </section>

    <section class="dashboard-overview-grid">
      <SectionCard
        title="当前关注设备风险"
        description="展示默认关注设备的最新风险预测结果，健康度、风险分数和告警等级均以接口返回为准。"
      >
        <template #headerActions>
          <RiskTag
            v-if="latestPrediction"
            :level="latestPrediction.alert_level"
            :score="latestPrediction.risk_score"
          />
          <RouterLink
            class="secondary-link"
            :to="{ name: 'predictions', query: { device_id: DEFAULT_DASHBOARD_DEVICE_ID } }"
          >
            查看风险预测
          </RouterLink>
        </template>

        <LoadingBlock
          v-if="predictionState.loading"
          text="正在加载最新风险结果..."
          height="280px"
        />
        <ErrorState
          v-else-if="predictionState.error"
          title="风险结果加载失败"
          :message="predictionState.error"
          @retry="loadDashboard"
        />
        <EmptyState
          v-else-if="!latestPrediction"
          title="暂无风险结果"
          description="默认关注设备尚未返回最新风险预测结果。"
        />
        <div v-else class="risk-overview">
          <div class="risk-overview__hero">
            <div class="risk-overview__identity">
              <span class="dashboard-kicker">观测对象</span>
              <h3>{{ focusedDeviceTitle }}</h3>
              <p>{{ riskSummaryText }}</p>
              <div class="risk-overview__tags">
                <RiskTag :level="latestPrediction.alert_level" :score="latestPrediction.risk_score" />
                <HealthBadge :score="latestPrediction.health_score" />
                <StatusTag
                  :value="focusedDevice?.device_status"
                  :type="focusedDeviceStatus.tone"
                  :label="focusedDeviceStatus.label"
                />
              </div>
            </div>

            <div class="risk-score-grid">
              <article class="score-panel">
                <span>风险分数</span>
                <strong>{{ formatNumber(latestPrediction.risk_score, 2) }}</strong>
                <div class="score-bar">
                  <span
                    class="score-bar__fill score-bar__fill--risk"
                    :style="{ width: `${riskProgress}%` }"
                  ></span>
                </div>
                <small>风险越高越需优先复核</small>
              </article>
              <article class="score-panel">
                <span>健康度</span>
                <strong>{{ formatNumber(latestPrediction.health_score, 1) }}</strong>
                <div class="score-bar">
                  <span
                    :class="['score-bar__fill', `score-bar__fill--${healthTone}`]"
                    :style="{ width: `${healthProgress}%` }"
                  ></span>
                </div>
                <small>健康度越低风险越高</small>
              </article>
            </div>
          </div>

          <div class="risk-meta-grid">
            <div v-for="item in predictionMetaItems" :key="item.label" class="risk-meta-item">
              <span>{{ item.label }}</span>
              <strong :title="item.value">{{ item.value }}</strong>
            </div>
          </div>

          <p v-if="defaultDeviceError" class="dashboard-inline-warning">
            默认设备详情加载失败：{{ defaultDeviceError }}
          </p>
        </div>
      </SectionCard>

      <SectionCard
        title="健康度概览"
        description="按健康度区间表达设备当前状态：0-30 危险，30-70 关注，70-100 正常。"
      >
        <LoadingBlock
          v-if="predictionState.loading"
          text="正在加载健康度结果..."
          height="280px"
        />
        <ErrorState
          v-else-if="predictionState.error"
          title="健康度暂不可用"
          :message="predictionState.error"
          @retry="loadDashboard"
        />
        <EmptyState
          v-else-if="!latestPrediction"
          title="暂无健康度"
          description="等待风险预测接口返回 health_score 后展示健康度状态。"
        />
        <div v-else class="health-overview">
          <div :class="['health-gauge', `health-gauge--${healthTone}`]">
            <span>健康度</span>
            <strong>{{ formatNumber(latestPrediction.health_score, 1) }}</strong>
            <HealthBadge :score="latestPrediction.health_score" />
          </div>

          <div class="health-scale" aria-hidden="true">
            <span class="health-scale__danger"></span>
            <span class="health-scale__warning"></span>
            <span class="health-scale__success"></span>
          </div>
          <div class="health-scale-labels">
            <span>危险 0-30</span>
            <span>关注 30-70</span>
            <span>正常 70-100</span>
          </div>

          <div class="health-detail-list">
            <div>
              <span>风险波动</span>
              <strong>{{ formatNumber(latestPrediction.risk_std, 3) }}</strong>
            </div>
            <div>
              <span>模型版本</span>
              <strong>{{ displayValue(latestPrediction.model_version) }}</strong>
            </div>
            <div>
              <span>时间窗口</span>
              <strong>{{ predictionWindowText }}</strong>
            </div>
          </div>
        </div>
      </SectionCard>
    </section>

    <SectionCard
      title="风险与健康度趋势"
      description="基于默认设备历史风险结果展示风险分数和健康度变化，时间范围使用当前 mock 数据稳定窗口。"
    >
      <template #headerActions>
        <span class="status-pill status-pill--default">设备 ID {{ DEFAULT_DASHBOARD_DEVICE_ID }}</span>
        <span class="status-pill status-pill--muted">{{ historyRangeText }}</span>
      </template>

      <div class="trend-chart-grid">
        <MetricTrendChart
          title="风险趋势"
          description="展示风险分数随时间变化，数值越高表示故障风险越高。"
          metric-name="风险分数"
          :points="riskTrendPoints"
          :loading="historyState.loading"
          :error="historyState.error"
          height="300px"
        />
        <MetricTrendChart
          title="健康度趋势"
          description="展示 health_score 随时间变化，仅使用服务端返回值。"
          metric-name="健康度"
          :points="healthTrendPoints"
          :loading="historyState.loading"
          :error="historyState.error"
          height="300px"
        />
      </div>
    </SectionCard>

    <section class="dashboard-list-grid">
      <SectionCard
        title="重点设备"
        description="展示设备台账前 5 条设备，结合基础状态提供快速详情入口。"
      >
        <template #headerActions>
          <RouterLink class="secondary-link" to="/devices">进入设备台账</RouterLink>
        </template>

        <LoadingBlock
          v-if="devicesState.loading"
          text="正在加载重点设备..."
          height="260px"
        />
        <ErrorState
          v-else-if="devicesState.error"
          title="设备数据加载失败"
          :message="devicesState.error"
          @retry="loadDashboard"
        />
        <EmptyState
          v-else-if="!keyDevices.length"
          title="暂无设备数据"
          description="设备台账接口当前未返回可展示设备。"
        />
        <div v-else class="table-shell dashboard-table-shell">
          <table class="status-table dashboard-table">
            <thead>
              <tr>
                <th>设备 ID</th>
                <th>车号</th>
                <th>ATP 类型</th>
                <th>配属铁路局</th>
                <th>设备状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in keyDevices" :key="item.device_id">
                <td class="dashboard-mono">{{ displayValue(item.device_id) }}</td>
                <td>{{ displayValue(item.car_no) }}</td>
                <td>{{ displayValue(item.atp_type) }}</td>
                <td>{{ displayValue(item.attach_bureau) }}</td>
                <td>
                  <StatusTag
                    :value="item.device_status"
                    :type="getDeviceStatusMeta(item.device_status).tone"
                    :label="getDeviceStatusMeta(item.device_status).label"
                    size="small"
                  />
                </td>
                <td>
                  <RouterLink
                    v-if="item.device_id"
                    class="table-link"
                    :to="{ name: 'device-detail', params: { id: item.device_id } }"
                  >
                    查看详情
                  </RouterLink>
                  <span v-else>--</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard
        title="最新告警"
        description="展示最近告警记录，处理动作保留在告警中心完成。"
      >
        <template #headerActions>
          <RouterLink class="secondary-link" to="/alerts">进入告警中心</RouterLink>
        </template>

        <LoadingBlock
          v-if="alertsState.loading"
          text="正在加载最新告警..."
          height="260px"
        />
        <ErrorState
          v-else-if="alertsState.error"
          title="告警数据加载失败"
          :message="alertsState.error"
          @retry="loadDashboard"
        />
        <EmptyState
          v-else-if="!latestAlerts.length"
          title="暂无告警记录"
          description="当前告警接口未返回可展示记录。"
        />
        <ul v-else class="dashboard-alert-list">
          <li v-for="item in latestAlerts" :key="item.key" class="dashboard-alert-item">
            <div class="dashboard-alert-item__header">
              <RiskTag :level="item.alert_level" size="small" />
              <StatusTag :value="item.alert_status" size="small" />
              <span>{{ item.timeText }}</span>
            </div>
            <strong>设备 {{ displayValue(item.device_id) }}</strong>
            <p>{{ displayValue(item.message) }}</p>
          </li>
        </ul>
      </SectionCard>
    </section>

    <SectionCard
      title="快捷入口"
      description="围绕设备台账、运行监测、风险预测和告警中心组织常用业务入口。"
    >
      <div class="quick-link-grid">
        <QuickLinkCard
          v-for="item in DASHBOARD_QUICK_LINKS"
          :key="item.to"
          :item="item"
        />
      </div>
    </SectionCard>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { MetricTrendChart } from '../components/chart'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import HealthBadge from '../components/common/HealthBadge.vue'
import LoadingBlock from '../components/common/LoadingBlock.vue'
import PageHeader from '../components/common/PageHeader.vue'
import RiskTag from '../components/common/RiskTag.vue'
import SectionCard from '../components/common/SectionCard.vue'
import StatCard from '../components/common/StatCard.vue'
import StatusTag from '../components/common/StatusTag.vue'
import QuickLinkCard from '../components/dashboard/QuickLinkCard.vue'
import { getAlertList } from '../api/alert'
import { getDeviceDetail, getDeviceList } from '../api/device'
import { getHealthStatus } from '../api/health'
import { getLatestPrediction, getPredictionHistory } from '../api/prediction'
import {
  DASHBOARD_ALERT_LIST_PARAMS,
  DASHBOARD_DEVICE_LIST_PARAMS,
  DASHBOARD_PREDICTION_HISTORY_PARAMS,
  DASHBOARD_QUICK_LINKS,
  DEFAULT_DASHBOARD_DEVICE_ID
} from '../constants/dashboard'
import {
  formatDateTime,
  formatModelVersion,
  formatWindowRange,
  getDeviceStatusMeta,
  getHealthStatusMeta,
  getServiceStatusMeta,
  toHealthProgress,
  toRiskProgress
} from '../utils/dashboard'
import { resolveRiskMeta } from '../utils/status'
import { getStoredRole } from '../utils/auth'

const serviceState = ref(createAsyncState(null))
const devicesState = ref(createListState())
const alertsState = ref(createListState())
const predictionState = ref(createAsyncState(null))
const historyState = ref(createListState())
const focusedDevice = ref(null)
const defaultDeviceError = ref('')
const lastLoadedAt = ref(null)
const now = ref(new Date())

let clockTimer = 0

const isRefreshing = computed(
  () =>
    serviceState.value.loading ||
    devicesState.value.loading ||
    alertsState.value.loading ||
    predictionState.value.loading ||
    historyState.value.loading
)

const currentRoleText = computed(() => {
  const role = getStoredRole()
  const roleMap = {
    ADMIN: '系统管理员',
    OPS: '运维用户'
  }

  return roleMap[role] || '当前用户'
})

const systemStatus = computed(() => {
  if (serviceState.value.loading) {
    return {
      label: '服务检查中',
      tone: 'muted'
    }
  }

  if (serviceState.value.error) {
    return {
      label: '服务异常',
      tone: 'danger'
    }
  }

  const meta = getServiceStatusMeta(serviceState.value.data?.status)
  return {
    label: meta.label,
    tone: meta.tone === 'success' ? 'success' : 'warning'
  }
})

const headerMetaText = computed(() => {
  const currentText = formatDateTime(now.value)
  const updatedText = lastLoadedAt.value ? formatDateTime(lastLoadedAt.value) : '尚未更新'
  return `当前时间 ${currentText} · 最近更新 ${updatedText}`
})

const deviceTotal = computed(() => devicesState.value.total || devicesState.value.list.length)
const normalDeviceCount = computed(
  () => devicesState.value.list.filter((item) => Number(item?.device_status) === 1).length
)
const pendingAlertCount = computed(
  () =>
    alertsState.value.list.filter((item) =>
      ['PENDING', 'PROCESSING'].includes(String(item?.alert_status || '').toUpperCase())
    ).length
)
const currentRiskMeta = computed(() =>
  resolveRiskMeta(latestPrediction.value?.alert_level, latestPrediction.value?.risk_score)
)

const overviewMetrics = computed(() => [
  {
    key: 'devices',
    label: '设备总数',
    value: devicesState.value.loading ? null : deviceTotal.value,
    description: '纳入系统监测与管理的 ATP 设备总量',
    trend: devicesState.value.error ? '设备接口异常' : '数据来源：设备台账',
    helper: devicesState.value.error || 'GET /api/v1/devices',
    type: devicesState.value.error ? 'warning' : 'primary',
    loading: devicesState.value.loading,
    error: devicesState.value.error
  },
  {
    key: 'normal',
    label: '正常设备数',
    value: devicesState.value.loading ? null : normalDeviceCount.value,
    description: 'device_status 为 1 的设备数量',
    trend: devicesState.value.error ? '暂不可统计' : `${deviceTotal.value} 台设备中已统计`,
    helper: devicesState.value.error || '按当前设备列表统计',
    type: devicesState.value.error ? 'warning' : 'success',
    loading: devicesState.value.loading,
    error: devicesState.value.error
  },
  {
    key: 'risk',
    label: '当前风险等级',
    value: predictionState.value.loading ? null : currentRiskMeta.value.label,
    description: '默认关注设备最新一次风险结果',
    trend: predictionState.value.error
      ? '风险接口异常'
      : `风险分数 ${formatNumber(latestPrediction.value?.risk_score, 2)}`,
    helper: predictionState.value.error || 'GET /api/v1/predictions/latest',
    type: predictionState.value.error ? 'warning' : currentRiskMeta.value.type,
    loading: predictionState.value.loading,
    error: predictionState.value.error
  },
  {
    key: 'pending-alerts',
    label: '未处理告警数',
    value: alertsState.value.loading ? null : pendingAlertCount.value,
    description: 'PENDING 或 PROCESSING 状态告警数量',
    trend: alertsState.value.error ? '暂不可统计' : '用于提示当前处理压力',
    helper: alertsState.value.error || '基于当前分页返回记录统计',
    type: pendingAlertCount.value > 0 ? 'warning' : 'success',
    loading: alertsState.value.loading,
    error: alertsState.value.error
  }
])

const latestPrediction = computed(() => predictionState.value.data)
const focusedDeviceStatus = computed(() => getDeviceStatusMeta(focusedDevice.value?.device_status))
const focusedDeviceTitle = computed(() => {
  const device = focusedDevice.value
  if (!device) {
    return `设备 ${DEFAULT_DASHBOARD_DEVICE_ID}`
  }

  return `${displayValue(device.car_no)} / 设备 ${displayValue(device.device_id)}`
})

const riskProgress = computed(() => toRiskProgress(latestPrediction.value?.risk_score))
const healthProgress = computed(() => toHealthProgress(latestPrediction.value?.health_score))
const healthMeta = computed(() => getHealthStatusMeta(latestPrediction.value?.health_score))
const healthTone = computed(() => healthMeta.value.tone || 'muted')
const riskSummaryText = computed(() => {
  if (!latestPrediction.value) {
    return '默认设备尚未返回风险预测结果。'
  }

  return `最新窗口结束于 ${formatDateTime(latestPrediction.value.window_end_time)}，当前健康状态为 ${healthMeta.value.label}。`
})
const predictionWindowText = computed(() =>
  latestPrediction.value
    ? formatWindowRange(latestPrediction.value.window_start_time, latestPrediction.value.window_end_time)
    : '未返回'
)
const predictionMetaItems = computed(() => {
  const item = latestPrediction.value || {}

  return [
    { label: '设备 ID', value: displayValue(item.device_id) },
    { label: '风险分数', value: formatNumber(item.risk_score, 2) },
    { label: '风险波动', value: formatNumber(item.risk_std, 3) },
    { label: '健康度', value: formatNumber(item.health_score, 1) },
    { label: '告警等级', value: displayValue(item.alert_level) },
    { label: '模型版本', value: formatModelVersion(item.model_version) },
    { label: '窗口开始', value: formatDateTime(item.window_start_time) },
    { label: '窗口结束', value: formatDateTime(item.window_end_time) }
  ]
})

const historyRangeText = computed(
  () => `${DASHBOARD_PREDICTION_HISTORY_PARAMS.start_time.slice(5, 16)} 至 ${DASHBOARD_PREDICTION_HISTORY_PARAMS.end_time.slice(5, 16)}`
)
const riskTrendPoints = computed(() =>
  historyState.value.list.map((item) => ({
    time: formatTrendTime(item.window_end_time || item.window_start_time),
    value: item.risk_score
  }))
)
const healthTrendPoints = computed(() =>
  historyState.value.list.map((item) => ({
    time: formatTrendTime(item.window_end_time || item.window_start_time),
    value: item.health_score
  }))
)

const keyDevices = computed(() => devicesState.value.list.slice(0, 5))
const latestAlerts = computed(() =>
  [...alertsState.value.list]
    .sort(
      (a, b) =>
        new Date(normalizeDateText(b.alert_time)).getTime() -
        new Date(normalizeDateText(a.alert_time)).getTime()
    )
    .slice(0, 5)
    .map((item, index) => ({
      ...item,
      key: item.alert_id || `${item.device_id || 'alert'}-${index}`,
      timeText: formatDateTime(item.alert_time)
    }))
)

async function loadDashboard() {
  serviceState.value = createAsyncState(null)
  devicesState.value = createListState()
  alertsState.value = createListState()
  predictionState.value = createAsyncState(null)
  historyState.value = createListState()
  focusedDevice.value = null
  defaultDeviceError.value = ''

  const [healthResult, deviceResult, alertResult, predictionResult, historyResult, deviceDetailResult] =
    await Promise.allSettled([
      getHealthStatus(),
      getDeviceList(DASHBOARD_DEVICE_LIST_PARAMS),
      getAlertList(DASHBOARD_ALERT_LIST_PARAMS),
      getLatestPrediction({ device_id: DEFAULT_DASHBOARD_DEVICE_ID }),
      getPredictionHistory(DASHBOARD_PREDICTION_HISTORY_PARAMS),
      getDeviceDetail(DEFAULT_DASHBOARD_DEVICE_ID)
    ])

  serviceState.value = resolveAsyncResult(healthResult, '系统健康状态加载失败')
  devicesState.value = resolveListResult(deviceResult, '设备台账加载失败')
  alertsState.value = resolveListResult(alertResult, '告警列表加载失败')
  predictionState.value = resolveAsyncResult(predictionResult, '最新风险结果加载失败', normalizePrediction)
  historyState.value = resolveListResult(historyResult, '历史趋势加载失败', normalizePrediction)

  if (deviceDetailResult.status === 'fulfilled') {
    focusedDevice.value = normalizePayload(deviceDetailResult.value) || null
  } else {
    defaultDeviceError.value = deviceDetailResult.reason?.message || '默认设备详情加载失败'
  }

  lastLoadedAt.value = new Date()
  now.value = new Date()
}

function createAsyncState(data) {
  return {
    loading: true,
    error: '',
    data
  }
}

function createListState() {
  return {
    loading: true,
    error: '',
    list: [],
    total: 0
  }
}

function resolveAsyncResult(result, fallbackMessage, normalizer = (value) => value) {
  if (result.status === 'fulfilled') {
    return {
      loading: false,
      error: '',
      data: normalizer(normalizePayload(result.value))
    }
  }

  return {
    loading: false,
    error: result.reason?.message || fallbackMessage,
    data: null
  }
}

function resolveListResult(result, fallbackMessage, normalizer = (value) => value) {
  if (result.status !== 'fulfilled') {
    return {
      loading: false,
      error: result.reason?.message || fallbackMessage,
      list: [],
      total: 0
    }
  }

  const payload = normalizePayload(result.value)
  const items = extractItems(payload).map((item) => normalizer(item)).filter(Boolean)

  return {
    loading: false,
    error: '',
    list: items,
    total: typeof payload?.total === 'number' ? payload.total : items.length
  }
}

function normalizePayload(result) {
  if (!result || typeof result !== 'object') {
    return null
  }

  return 'data' in result ? result.data : result
}

function extractItems(payload) {
  if (Array.isArray(payload)) {
    return payload
  }

  if (!payload || typeof payload !== 'object') {
    return []
  }

  const candidates = [payload.items, payload.records, payload.list, payload.rows, payload.data]
  return candidates.find((item) => Array.isArray(item)) || []
}

function normalizePrediction(record) {
  if (!record || typeof record !== 'object') {
    return null
  }

  return {
    ...record,
    risk_score: toFiniteNumber(record.risk_score ?? record.calibrated_risk_score),
    risk_std: toFiniteNumber(record.risk_std),
    health_score: toFiniteNumber(record.health_score)
  }
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}

function formatNumber(value, digits = 2) {
  const normalizedValue = toFiniteNumber(value)
  return normalizedValue === null ? '--' : normalizedValue.toFixed(digits)
}

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '--' : String(value)
}

function formatTrendTime(value) {
  return formatDateTime(value, '--').replace(/^(\d{4})\//, '').replace(' ', '\n')
}

function normalizeDateText(value) {
  return value ? String(value).replace(' ', 'T') : ''
}

onMounted(() => {
  loadDashboard()
  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 60 * 1000)
})

onBeforeUnmount(() => {
  if (clockTimer) {
    window.clearInterval(clockTimer)
    clockTimer = 0
  }
})
</script>

<style scoped>
.dashboard-page {
  display: grid;
  gap: var(--space-6);
}

.dashboard-stat-grid {
  align-items: stretch;
}

.dashboard-card-hint,
.dashboard-inline-warning {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.dashboard-card-hint--error,
.dashboard-inline-warning {
  color: var(--color-danger);
}

.dashboard-overview-grid,
.dashboard-list-grid {
  display: grid;
  gap: var(--space-5);
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, 0.9fr);
  align-items: start;
}

.dashboard-list-grid {
  grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
}

.risk-overview,
.health-overview {
  display: grid;
  gap: var(--space-5);
}

.risk-overview__hero {
  display: grid;
  gap: var(--space-5);
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.86fr);
  align-items: stretch;
}

.risk-overview__identity {
  display: grid;
  align-content: start;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-soft);
}

.dashboard-kicker {
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 760;
}

.risk-overview__identity h3,
.risk-overview__identity p {
  margin: 0;
}

.risk-overview__identity h3 {
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.risk-overview__identity p {
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

.risk-overview__tags,
.dashboard-alert-item__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.risk-score-grid {
  display: grid;
  gap: var(--space-4);
}

.score-panel {
  display: grid;
  align-content: center;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: #ffffff;
}

.score-panel span,
.score-panel small,
.risk-meta-item span,
.health-detail-list span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.score-panel strong {
  color: var(--color-text-primary);
  font-size: 2rem;
  line-height: 1;
}

.score-bar,
.health-scale {
  width: 100%;
  height: 10px;
  overflow: hidden;
  border-radius: var(--radius-pill);
  background: var(--color-neutral-soft);
}

.score-bar__fill {
  display: block;
  height: 100%;
  min-width: 3px;
  border-radius: inherit;
}

.score-bar__fill--risk,
.score-bar__fill--danger {
  background: var(--color-danger);
}

.score-bar__fill--warning {
  background: var(--color-warning);
}

.score-bar__fill--success {
  background: var(--color-success);
}

.score-bar__fill--muted {
  background: var(--color-neutral);
}

.risk-meta-grid {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.risk-meta-item,
.health-detail-list > div {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-soft);
}

.risk-meta-item strong,
.health-detail-list strong {
  min-width: 0;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.health-gauge {
  display: grid;
  place-items: center;
  gap: var(--space-3);
  min-height: 190px;
  border: 1px solid var(--health-border);
  border-radius: var(--radius-xl);
  background: var(--health-bg);
}

.health-gauge span {
  color: var(--color-text-secondary);
  font-weight: 700;
}

.health-gauge strong {
  color: var(--health-color);
  font-size: 3rem;
  line-height: 1;
}

.health-gauge--danger {
  --health-bg: var(--color-danger-soft);
  --health-border: var(--color-danger-border);
  --health-color: var(--color-danger);
}

.health-gauge--warning {
  --health-bg: var(--color-warning-soft);
  --health-border: var(--color-warning-border);
  --health-color: var(--color-warning);
}

.health-gauge--success {
  --health-bg: var(--color-success-soft);
  --health-border: var(--color-success-border);
  --health-color: var(--color-success);
}

.health-gauge--muted {
  --health-bg: var(--color-neutral-soft);
  --health-border: var(--color-neutral-border);
  --health-color: var(--color-neutral);
}

.health-scale {
  display: grid;
  grid-template-columns: 30fr 40fr 30fr;
  height: 12px;
}

.health-scale span {
  display: block;
}

.health-scale__danger {
  background: var(--color-danger);
}

.health-scale__warning {
  background: var(--color-warning);
}

.health-scale__success {
  background: var(--color-success);
}

.health-scale-labels,
.health-detail-list {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.health-scale-labels {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.health-scale-labels span:nth-child(2) {
  text-align: center;
}

.health-scale-labels span:nth-child(3) {
  text-align: right;
}

.trend-chart-grid {
  display: grid;
  gap: var(--space-5);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dashboard-table-shell {
  border-radius: var(--radius-lg);
}

.dashboard-table {
  min-width: 720px;
}

.dashboard-mono {
  color: var(--color-text-primary);
  font-family: var(--font-family-mono);
  font-weight: 700;
}

.dashboard-alert-list {
  display: grid;
  gap: var(--space-3);
  padding: 0;
  margin: 0;
  list-style: none;
}

.dashboard-alert-item {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-soft);
}

.dashboard-alert-item__header span:last-child {
  margin-left: auto;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.dashboard-alert-item strong,
.dashboard-alert-item p {
  margin: 0;
}

.dashboard-alert-item strong {
  color: var(--color-text-primary);
}

.dashboard-alert-item p {
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

.quick-link-grid {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

@media (max-width: 1280px) {
  .risk-meta-grid,
  .quick-link-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .dashboard-overview-grid,
  .dashboard-list-grid,
  .trend-chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .risk-overview__hero,
  .risk-meta-grid,
  .health-scale-labels,
  .health-detail-list,
  .quick-link-grid {
    grid-template-columns: 1fr;
  }

  .health-scale-labels span,
  .health-scale-labels span:nth-child(2),
  .health-scale-labels span:nth-child(3) {
    text-align: left;
  }

  .dashboard-alert-item__header span:last-child {
    margin-left: 0;
  }
}
</style>
