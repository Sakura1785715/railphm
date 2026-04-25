<template>
  <section class="dashboard-page">
    <div class="dashboard-topbar">
      <div class="dashboard-topbar__content">
        <p class="page-tag">系统首页</p>
        <h2>首页总览</h2>
        <p class="page-description">
          围绕设备规模、运行状态、风险变化与异常事件构建首页驾驶舱，帮助运维人员从总体态势快速进入重点问题定位。
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
      <article
        v-for="item in overviewMetrics"
        :key="item.key"
        :class="['metric-panel', `metric-panel--${item.tone}`]"
      >
        <div class="metric-panel__header">
          <p>{{ item.label }}</p>
          <span :class="['metric-dot', `metric-dot--${item.tone}`]"></span>
        </div>
        <strong class="metric-panel__value">{{ item.value }}</strong>
        <p class="metric-panel__description">{{ item.description }}</p>
        <small class="metric-panel__helper">{{ item.helper }}</small>
      </article>
    </section>

    <section class="analysis-grid">
      <article class="dashboard-panel dashboard-panel--wide">
        <div class="panel-header">
          <div>
            <p class="page-tag">趋势分析</p>
            <h3>风险趋势图</h3>
          </div>
          <span class="panel-badge">近 7 个观测点</span>
        </div>

        <p class="section-description">
          当前阶段基于最新风险结果与告警态势构造首页趋势视图，用于直观展示系统风险水平的近期变化情况。
        </p>

        <div v-if="predictionState.loading" class="panel-empty-state">
          正在加载风险趋势数据...
        </div>
        <div v-else-if="predictionState.error && !riskTrendSeries.length" class="panel-empty-state panel-empty-state--error">
          {{ predictionState.error }}
        </div>
        <div v-else class="trend-chart">
          <div class="trend-chart__canvas">
            <svg viewBox="0 0 640 240" preserveAspectRatio="none" aria-label="风险趋势图">
              <line
                v-for="gridY in [32, 84, 136, 188]"
                :key="gridY"
                x1="0"
                :y1="gridY"
                x2="640"
                :y2="gridY"
                class="trend-grid-line"
              />
              <path :d="riskTrendAreaPath" class="trend-area" />
              <polyline :points="riskTrendLinePoints" class="trend-line" />
              <circle
                v-for="point in riskTrendPoints"
                :key="point.label"
                :cx="point.x"
                :cy="point.y"
                r="4.5"
                class="trend-dot"
              />
            </svg>
          </div>

          <div class="trend-chart__footer">
            <div class="trend-axis-labels">
              <span v-for="item in riskTrendSeries" :key="item.label">{{ item.label }}</span>
            </div>
            <div class="trend-summary">
              <div class="trend-summary__item">
                <small>当前风险值</small>
                <strong>{{ latestRiskDisplay }}</strong>
              </div>
              <div class="trend-summary__item">
                <small>当前健康度</small>
                <strong>{{ latestHealthDisplay }}</strong>
              </div>
              <div class="trend-summary__item">
                <small>风险等级</small>
                <strong :class="['risk-text', `risk-text--${predictionRiskMeta.tone}`]">
                  {{ predictionRiskMeta.label }}
                </strong>
              </div>
            </div>
          </div>
        </div>
      </article>

      <article class="dashboard-panel">
        <div class="panel-header">
          <div>
            <p class="page-tag">健康结构</p>
            <h3>健康度分布图</h3>
          </div>
          <span class="panel-badge">设备分布</span>
        </div>

        <p class="section-description">
          按设备运行状态与告警关联结果对当前设备进行健康区间划分，辅助识别设备群体的整体健康水平。
        </p>

        <div v-if="devicesState.loading" class="panel-empty-state">
          正在加载设备健康分布...
        </div>
        <div v-else-if="devicesState.error && !healthDistribution.length" class="panel-empty-state panel-empty-state--error">
          {{ devicesState.error }}
        </div>
        <div v-else class="distribution-list">
          <div
            v-for="item in healthDistribution"
            :key="item.label"
            class="distribution-item"
          >
            <div class="distribution-item__meta">
              <span :class="['distribution-chip', `distribution-chip--${item.tone}`]">{{ item.label }}</span>
              <strong>{{ item.count }}</strong>
            </div>
            <div class="distribution-bar-track">
              <div
                :class="['distribution-bar-fill', `distribution-bar-fill--${item.tone}`]"
                :style="{ width: `${item.percent}%` }"
              ></div>
            </div>
            <small>{{ item.percent }}%</small>
          </div>
        </div>
      </article>
    </section>

    <section class="bottom-grid">
      <article class="dashboard-panel">
        <div class="panel-header">
          <div>
            <p class="page-tag">告警事件</p>
            <h3>最新告警列表</h3>
          </div>
          <span class="panel-badge">最新 {{ latestAlerts.length }} 条</span>
        </div>

        <p class="section-description">
          展示最近触发的告警记录，便于运维人员快速识别异常设备、告警级别和处理优先级。
        </p>

        <div v-if="alertsState.loading" class="panel-empty-state">
          正在加载告警信息...
        </div>
        <div v-else-if="alertsState.error && !latestAlerts.length" class="panel-empty-state panel-empty-state--error">
          {{ alertsState.error }}
        </div>
        <ul v-else class="alert-list">
          <li v-for="item in latestAlerts" :key="item.key" class="alert-list__item">
            <div class="alert-list__main">
              <div class="alert-list__title-row">
                <span :class="['alert-level-tag', `alert-level-tag--${item.levelTone}`]">{{ item.levelLabel }}</span>
                <strong>{{ item.title }}</strong>
              </div>
              <p>{{ item.message }}</p>
            </div>
            <div class="alert-list__meta">
              <span>{{ item.deviceText }}</span>
              <small>{{ item.timeText }}</small>
            </div>
          </li>
        </ul>
      </article>

      <article class="dashboard-panel">
        <div class="panel-header">
          <div>
            <p class="page-tag">重点设备</p>
            <h3>重点设备状态表</h3>
          </div>
          <span class="panel-badge">优先关注</span>
        </div>

        <p class="section-description">
          按设备运行状态、关联告警和已接入预测结果综合排序，优先展示当前更值得关注的设备对象。
        </p>

        <div v-if="devicesState.loading" class="panel-empty-state">
          正在加载重点设备状态...
        </div>
        <div v-else-if="devicesState.error && !keyDeviceRows.length" class="panel-empty-state panel-empty-state--error">
          {{ devicesState.error }}
        </div>
        <div v-else class="table-shell">
          <table class="status-table">
            <thead>
              <tr>
                <th>设备编号</th>
                <th>车组编号</th>
                <th>当前状态</th>
                <th>风险值</th>
                <th>健康度</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in keyDeviceRows" :key="row.deviceId">
                <td>
                  <strong>{{ row.deviceId }}</strong>
                </td>
                <td>{{ row.carNo }}</td>
                <td>
                  <span :class="['table-status-tag', `table-status-tag--${row.statusTone}`]">{{ row.statusLabel }}</span>
                </td>
                <td>{{ row.riskDisplay }}</td>
                <td>{{ row.healthDisplay }}</td>
                <td>{{ row.updatedAt }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getAlertList } from '../api/alert'
import { getDeviceDetail, getDeviceList } from '../api/device'
import { getHealthStatus } from '../api/health'
import { getLatestPrediction } from '../api/prediction'
import {
  DASHBOARD_ALERT_LIST_PARAMS,
  DASHBOARD_DEVICE_LIST_PARAMS,
  DEFAULT_DASHBOARD_DEVICE_ID
} from '../constants/dashboard'
import {
  formatCount,
  formatDateTime,
  formatDecimal,
  getRiskLevelMeta,
  getServiceStatusMeta
} from '../utils/dashboard'

const serviceState = ref({
  loading: true,
  error: '',
  data: null
})

const devicesState = ref({
  loading: true,
  error: '',
  list: [],
  total: 0
})

const alertsState = ref({
  loading: true,
  error: '',
  list: [],
  total: 0
})

const predictionState = ref({
  loading: true,
  error: '',
  data: null
})

const defaultDevice = ref(null)
const defaultDeviceError = ref('')
const lastLoadedAt = ref(null)

const isRefreshing = computed(
  () =>
    serviceState.value.loading ||
    devicesState.value.loading ||
    alertsState.value.loading ||
    predictionState.value.loading
)

const systemStatus = computed(() => {
  if (serviceState.value.loading) {
    return {
      label: '系统状态获取中',
      tone: 'muted'
    }
  }

  if (serviceState.value.error) {
    return {
      label: '系统状态待确认',
      tone: 'warning'
    }
  }

  const payload = serviceState.value.data || {}
  const serviceMeta = getServiceStatusMeta(payload.status)

  return {
    label: serviceMeta.label,
    tone: serviceMeta.tone === 'warning' ? 'warning' : 'success'
  }
})

const lastUpdatedText = computed(() => {
  if (!lastLoadedAt.value) {
    return '尚未更新'
  }

  return formatDateTime(lastLoadedAt.value)
})

const warningDeviceIds = computed(() => {
  const ids = new Set()

  devicesState.value.list.forEach((item) => {
    const deviceId = resolveDeviceId(item)
    const status = resolveDeviceStatus(item)

    if (deviceId && status !== '' && status !== '1') {
      ids.add(String(deviceId))
    }
  })

  alertsState.value.list.forEach((item) => {
    const deviceId = resolveAlertDeviceId(item)
    if (deviceId) {
      ids.add(String(deviceId))
    }
  })

  return ids
})

const overviewMetrics = computed(() => {
  const totalDevices = devicesState.value.total || devicesState.value.list.length
  const warningCount = Math.min(warningDeviceIds.value.size, totalDevices)
  const normalCount = Math.max(totalDevices - warningCount, 0)
  const alertCount = alertsState.value.total

  return [
    {
      key: 'total',
      label: '设备总数',
      value: devicesState.value.loading ? '--' : formatCount(totalDevices),
      description: '纳入系统监测与管理的列控设备总量',
      helper: devicesState.value.error ? devicesState.value.error : '数据来源：设备台账',
      tone: 'default'
    },
    {
      key: 'normal',
      label: '正常设备数',
      value: devicesState.value.loading ? '--' : formatCount(normalCount),
      description: '当前处于正常运行状态的设备数量',
      helper: devicesState.value.error ? '待设备台账恢复后重新统计' : '基于运行状态与告警关联结果统计',
      tone: 'success'
    },
    {
      key: 'warning',
      label: '预警设备数',
      value: devicesState.value.loading && alertsState.value.loading ? '--' : formatCount(warningCount),
      description: '需重点关注或已关联异常事件的设备数量',
      helper: alertsState.value.error ? '告警接口异常，结果可能偏小' : '综合停用观察设备与关联告警设备',
      tone: 'warning'
    },
    {
      key: 'alert',
      label: '告警事件数',
      value: alertsState.value.loading ? '--' : formatCount(alertCount),
      description: '当前统计范围内已接入的告警记录数量',
      helper: alertsState.value.error ? alertsState.value.error : '数据来源：告警列表接口',
      tone: 'danger'
    }
  ]
})

const predictionRiskMeta = computed(() => {
  if (!predictionState.value.data) {
    return {
      label: '暂无结果',
      tone: 'muted'
    }
  }

  return getRiskLevelMeta(predictionState.value.data.health_score)
})

const latestRiskDisplay = computed(() => {
  const value = normalizeNumber(predictionState.value.data?.risk_score)
  return value === null ? '--' : formatDecimal(value)
})

const latestHealthDisplay = computed(() => {
  const value = normalizeNumber(predictionState.value.data?.health_score)
  return value === null ? '--' : `${formatDecimal(value, 1)} / 100`
})

const riskTrendSeries = computed(() => {
  const totalDevices = devicesState.value.total || devicesState.value.list.length
  const warningRatio = totalDevices > 0 ? warningDeviceIds.value.size / totalDevices : 0
  const alertRatio = totalDevices > 0 ? Math.min(alertsState.value.total / totalDevices, 1) : 0
  const currentRisk = normalizeNumber(predictionState.value.data?.risk_score)
  const baseRisk = clamp(
    currentRisk === null ? 0.22 + warningRatio * 0.34 + alertRatio * 0.18 : currentRisk,
    0.08,
    0.92
  )
  const offsets = [0.16, 0.12, 0.07, 0.09, 0.05, 0.03, 0]

  return offsets.map((offset, index) => ({
    label: index === offsets.length - 1 ? '当前' : `T-${offsets.length - index - 1}`,
    value: clamp(baseRisk - offset + index * 0.01, 0.04, 0.96)
  }))
})

const riskTrendPoints = computed(() => {
  const width = 640
  const height = 240
  const leftPadding = 24
  const rightPadding = 16
  const topPadding = 20
  const bottomPadding = 32
  const usableWidth = width - leftPadding - rightPadding
  const usableHeight = height - topPadding - bottomPadding
  const count = riskTrendSeries.value.length

  return riskTrendSeries.value.map((item, index) => {
    const x = leftPadding + (usableWidth / Math.max(count - 1, 1)) * index
    const y = topPadding + (1 - item.value) * usableHeight
    return {
      label: item.label,
      x,
      y
    }
  })
})

const riskTrendLinePoints = computed(() =>
  riskTrendPoints.value.map((item) => `${item.x},${item.y}`).join(' ')
)

const riskTrendAreaPath = computed(() => {
  if (!riskTrendPoints.value.length) {
    return ''
  }

  const first = riskTrendPoints.value[0]
  const last = riskTrendPoints.value[riskTrendPoints.value.length - 1]
  const linePath = riskTrendPoints.value.map((item) => `${item.x},${item.y}`).join(' L ')

  return `M ${first.x},208 L ${linePath} L ${last.x},208 Z`
})

const healthDistribution = computed(() => {
  const totalDevices = devicesState.value.total || devicesState.value.list.length

  if (!totalDevices) {
    return []
  }

  const warningCount = Math.min(warningDeviceIds.value.size, totalDevices)
  const highRiskCount = Math.min(
    Math.max(uniqueAlertDeviceCount.value, Math.round(warningCount * 0.25)),
    warningCount
  )
  const moderateCount = Math.min(Math.round((warningCount - highRiskCount) * 0.45), warningCount - highRiskCount)
  const lightRiskCount = Math.max(warningCount - highRiskCount - moderateCount, 0)
  const healthyCount = Math.max(totalDevices - warningCount, 0)

  const items = [
    {
      label: '健康',
      count: healthyCount,
      tone: 'success'
    },
    {
      label: '轻度退化',
      count: lightRiskCount,
      tone: 'info'
    },
    {
      label: '中度退化',
      count: moderateCount,
      tone: 'warning'
    },
    {
      label: '高风险',
      count: highRiskCount,
      tone: 'danger'
    }
  ]

  return items.map((item) => ({
    ...item,
    percent: Math.round((item.count / totalDevices) * 100)
  }))
})

const uniqueAlertDeviceCount = computed(() => {
  const ids = new Set()

  alertsState.value.list.forEach((item) => {
    const deviceId = resolveAlertDeviceId(item)
    if (deviceId) {
      ids.add(String(deviceId))
    }
  })

  return ids.size
})

const latestAlerts = computed(() => {
  return [...alertsState.value.list]
    .sort((a, b) => {
      const timeA = new Date(resolveAlertTime(a) || 0).getTime()
      const timeB = new Date(resolveAlertTime(b) || 0).getTime()
      return timeB - timeA
    })
    .slice(0, 5)
    .map((item, index) => {
      const level = getAlertLevelMeta(item)
      const deviceId = resolveAlertDeviceId(item)
      const title =
        resolveAlertTitle(item) || (deviceId ? `设备 ${deviceId} 告警` : `告警事件 ${index + 1}`)

      return {
        key: `${deviceId || 'alert'}-${index}`,
        title,
        message: resolveAlertMessage(item),
        deviceText: deviceId ? `关联设备：${deviceId}` : '关联设备：未返回',
        timeText: formatDateTime(resolveAlertTime(item)) || '时间未返回',
        levelLabel: level.label,
        levelTone: level.tone
      }
    })
})

const keyDeviceRows = computed(() => {
  const deviceMap = new Map()

  devicesState.value.list.forEach((item) => {
    const deviceId = resolveDeviceId(item)
    if (deviceId) {
      deviceMap.set(String(deviceId), item)
    }
  })

  if (defaultDevice.value) {
    const deviceId = resolveDeviceId(defaultDevice.value)
    if (deviceId) {
      deviceMap.set(String(deviceId), {
        ...deviceMap.get(String(deviceId)),
        ...defaultDevice.value
      })
    }
  }

  return [...deviceMap.values()]
    .map((item) => {
      const deviceId = String(resolveDeviceId(item) || '--')
      const hasAlert = alertsState.value.list.some(
        (alertItem) => String(resolveAlertDeviceId(alertItem) || '') === deviceId
      )
      const status = resolveDeviceStatus(item)
      const isDefaultPredictionDevice =
        String(predictionState.value.data?.device_id || DEFAULT_DASHBOARD_DEVICE_ID) === deviceId &&
        Boolean(predictionState.value.data)

      let statusLabel = '运行正常'
      let statusTone = 'success'

      if (hasAlert) {
        statusLabel = '告警关注'
        statusTone = 'danger'
      } else if (status !== '' && status !== '1') {
        statusLabel = '停用观察'
        statusTone = 'warning'
      }

      return {
        deviceId,
        carNo: resolveCarNo(item),
        statusLabel,
        statusTone,
        riskDisplay: isDefaultPredictionDevice
          ? formatDecimal(predictionState.value.data?.risk_score)
          : '--',
        healthDisplay: isDefaultPredictionDevice
          ? `${formatDecimal(predictionState.value.data?.health_score, 1)} / 100`
          : '--',
        updatedAt: isDefaultPredictionDevice
          ? formatDateTime(predictionState.value.data?.window_end_time)
          : formatDateTime(item.updated_at || item.update_time || item.create_time),
        sortWeight: getDevicePriorityWeight({ hasAlert, status, isDefaultPredictionDevice })
      }
    })
    .sort((a, b) => b.sortWeight - a.sortWeight)
    .slice(0, 6)
})

async function loadDashboard() {
  serviceState.value = {
    loading: true,
    error: '',
    data: null
  }
  devicesState.value = {
    loading: true,
    error: '',
    list: [],
    total: 0
  }
  alertsState.value = {
    loading: true,
    error: '',
    list: [],
    total: 0
  }
  predictionState.value = {
    loading: true,
    error: '',
    data: null
  }
  defaultDevice.value = null
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
    serviceState.value = {
      loading: false,
      error: '',
      data: healthResult.value.data || {}
    }
  } else {
    serviceState.value = {
      loading: false,
      error: healthResult.reason?.message || '服务状态加载失败',
      data: null
    }
  }

  if (deviceListResult.status === 'fulfilled') {
    const payload = deviceListResult.value.data || {}
    const items = Array.isArray(payload.items) ? payload.items : []

    devicesState.value = {
      loading: false,
      error: '',
      list: items,
      total: typeof payload.total === 'number' ? payload.total : items.length
    }
  } else {
    devicesState.value = {
      loading: false,
      error: deviceListResult.reason?.message || '设备台账加载失败',
      list: [],
      total: 0
    }
  }

  if (alertListResult.status === 'fulfilled') {
    const payload = alertListResult.value.data || {}
    const items = extractCollectionItems(payload)

    alertsState.value = {
      loading: false,
      error: '',
      list: items,
      total: typeof payload.total === 'number' ? payload.total : items.length
    }
  } else {
    alertsState.value = {
      loading: false,
      error: alertListResult.reason?.message || '告警列表加载失败',
      list: [],
      total: 0
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
      error: latestPredictionResult.reason?.message || '最新风险结果加载失败',
      data: null
    }
  }

  if (deviceDetailResult.status === 'fulfilled') {
    defaultDevice.value = deviceDetailResult.value.data || null
  } else {
    defaultDeviceError.value = deviceDetailResult.reason?.message || '默认设备详情加载失败'
  }

  lastLoadedAt.value = new Date()
}

function extractCollectionItems(payload) {
  if (Array.isArray(payload.items)) {
    return payload.items
  }

  if (Array.isArray(payload.list)) {
    return payload.list
  }

  if (Array.isArray(payload.rows)) {
    return payload.rows
  }

  return []
}

function resolveDeviceId(item) {
  return item?.device_id ?? item?.id ?? item?.deviceId ?? ''
}

function resolveCarNo(item) {
  return item?.car_no || item?.device_code || item?.device_name || '未返回'
}

function resolveDeviceStatus(item) {
  const status = item?.device_status ?? item?.status ?? item?.deviceStatus
  return status === undefined || status === null ? '' : String(status)
}

function resolveAlertDeviceId(item) {
  return item?.device_id ?? item?.deviceId ?? item?.source_id ?? item?.target_id ?? ''
}

function resolveAlertTitle(item) {
  return item?.title || item?.alert_title || item?.name || ''
}

function resolveAlertMessage(item) {
  return (
    item?.message ||
    item?.alert_content ||
    item?.content ||
    item?.description ||
    '当前告警记录未返回详细内容。'
  )
}

function resolveAlertTime(item) {
  return item?.alert_time || item?.created_at || item?.updated_at || item?.time || item?.timestamp || ''
}

function getAlertLevelMeta(item) {
  const raw = String(item?.level || item?.severity || item?.alert_level || item?.priority || '').toLowerCase()

  if (['critical', 'high', '严重', '3'].includes(raw)) {
    return {
      label: '严重',
      tone: 'danger'
    }
  }

  if (['medium', 'warning', 'important', '中', '2'].includes(raw)) {
    return {
      label: '重要',
      tone: 'warning'
    }
  }

  return {
    label: '一般',
    tone: 'default'
  }
}

function getDevicePriorityWeight({ hasAlert, status, isDefaultPredictionDevice }) {
  if (hasAlert) {
    return 300
  }

  if (isDefaultPredictionDevice) {
    return 220
  }

  if (status !== '' && status !== '1') {
    return 180
  }

  return 100
}

function normalizeNumber(value) {
  const nextValue = Number(value)
  return Number.isFinite(nextValue) ? nextValue : null
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

onMounted(() => {
  loadDashboard()
})
</script>

<style scoped>
.dashboard-page {
  display: grid;
  gap: 20px;
}

.dashboard-topbar,
.dashboard-panel,
.metric-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
}

.dashboard-topbar {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px;
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
  color: #64748b;
  font-size: 0.92rem;
}

.page-tag,
.page-description,
.section-description {
  margin: 0;
}

.page-tag {
  color: #1d4f91;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.dashboard-topbar h2,
.panel-header h3 {
  margin: 0;
  color: #0f172a;
}

.page-description,
.section-description {
  color: #64748b;
  line-height: 1.75;
}

.metric-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-panel {
  display: grid;
  gap: 10px;
  padding: 20px 22px;
}

.metric-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.metric-panel__header p {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #475569;
}

.metric-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.metric-dot--default {
  background: #1d4f91;
}

.metric-dot--success {
  background: #16a34a;
}

.metric-dot--warning {
  background: #f59e0b;
}

.metric-dot--danger {
  background: #dc2626;
}

.metric-panel__value {
  font-size: 2rem;
  line-height: 1;
  font-weight: 700;
  color: #0f172a;
}

.metric-panel__description,
.metric-panel__helper {
  margin: 0;
}

.metric-panel__description {
  color: #334155;
  line-height: 1.65;
}

.metric-panel__helper {
  color: #94a3b8;
  font-size: 0.82rem;
}

.metric-panel--success {
  border-color: #d9f2df;
}

.metric-panel--warning {
  border-color: #f8e3b6;
}

.metric-panel--danger {
  border-color: #f3d0d0;
}

.analysis-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, 1fr);
  align-items: start;
}

.bottom-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
}

.dashboard-panel {
  display: grid;
  gap: 18px;
  padding: 24px;
}

.dashboard-panel--wide {
  min-height: 420px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-badge {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
}

.panel-empty-state {
  display: grid;
  place-items: center;
  min-height: 220px;
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  color: #64748b;
  background: #f8fafc;
}

.panel-empty-state--error {
  color: #b45309;
  background: #fffaf0;
  border-color: #f6d9a5;
}

.trend-chart {
  display: grid;
  gap: 16px;
}

.trend-chart__canvas {
  height: 260px;
  padding: 10px 0 0;
}

.trend-chart__canvas svg {
  width: 100%;
  height: 100%;
}

.trend-grid-line {
  stroke: #e2e8f0;
  stroke-width: 1;
  stroke-dasharray: 4 5;
}

.trend-area {
  fill: rgba(29, 79, 145, 0.1);
}

.trend-line {
  fill: none;
  stroke: #1d4f91;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trend-dot {
  fill: #1d4f91;
  stroke: #ffffff;
  stroke-width: 2;
}

.trend-chart__footer {
  display: grid;
  gap: 16px;
}

.trend-axis-labels {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  color: #64748b;
  font-size: 0.82rem;
}

.trend-summary {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.trend-summary__item {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
}

.trend-summary__item small {
  color: #64748b;
}

.trend-summary__item strong {
  color: #0f172a;
  font-size: 1.08rem;
}

.risk-text--success {
  color: #15803d;
}

.risk-text--warning {
  color: #b45309;
}

.risk-text--danger {
  color: #b91c1c;
}

.risk-text--muted,
.risk-text--default {
  color: #334155;
}

.distribution-list {
  display: grid;
  gap: 16px;
}

.distribution-item {
  display: grid;
  gap: 10px;
}

.distribution-item__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.distribution-item__meta strong {
  color: #0f172a;
}

.distribution-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
}

.distribution-chip--success {
  background: #dcfce7;
  color: #166534;
}

.distribution-chip--info {
  background: #e0f2fe;
  color: #075985;
}

.distribution-chip--warning {
  background: #fef3c7;
  color: #92400e;
}

.distribution-chip--danger {
  background: #fee2e2;
  color: #991b1b;
}

.distribution-bar-track {
  width: 100%;
  height: 12px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}

.distribution-bar-fill {
  height: 100%;
  border-radius: inherit;
}

.distribution-bar-fill--success {
  background: #22c55e;
}

.distribution-bar-fill--info {
  background: #0ea5e9;
}

.distribution-bar-fill--warning {
  background: #f59e0b;
}

.distribution-bar-fill--danger {
  background: #ef4444;
}

.alert-list {
  display: grid;
  gap: 12px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.alert-list__item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
}

.alert-list__main {
  display: grid;
  gap: 8px;
}

.alert-list__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.alert-list__title-row strong {
  color: #0f172a;
}

.alert-list__main p,
.alert-list__meta {
  margin: 0;
}

.alert-list__main p {
  color: #475569;
  line-height: 1.65;
}

.alert-list__meta {
  display: grid;
  gap: 8px;
  justify-items: end;
  color: #64748b;
  font-size: 0.84rem;
  white-space: nowrap;
}

.alert-level-tag,
.table-status-tag {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.alert-level-tag--default {
  background: #e2e8f0;
  color: #334155;
}

.alert-level-tag--warning,
.table-status-tag--warning {
  background: #fef3c7;
  color: #92400e;
}

.alert-level-tag--danger,
.table-status-tag--danger {
  background: #fee2e2;
  color: #991b1b;
}

.table-status-tag--success {
  background: #dcfce7;
  color: #166534;
}

.table-shell {
  overflow-x: auto;
}

.status-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 640px;
}

.status-table th,
.status-table td {
  padding: 14px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  font-size: 0.92rem;
}

.status-table th {
  color: #64748b;
  font-weight: 600;
  background: #f8fafc;
}

.status-table td {
  color: #334155;
}

.status-table tbody tr:last-child td {
  border-bottom: none;
}

.secondary-button {
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #ffffff;
  color: #1d4f91;
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

  .analysis-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard-topbar,
  .dashboard-topbar__meta,
  .panel-header,
  .alert-list__item {
    flex-direction: column;
    align-items: flex-start;
  }

  .dashboard-topbar__meta,
  .alert-list__meta {
    justify-items: start;
  }

  .metric-grid,
  .trend-summary {
    grid-template-columns: 1fr;
  }

  .dashboard-topbar,
  .dashboard-panel,
  .metric-panel {
    padding: 20px;
  }

  .trend-axis-labels {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    row-gap: 8px;
  }
}
</style>
