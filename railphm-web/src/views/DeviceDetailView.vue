<template>
  <section class="device-detail-page">
    <div v-if="deviceLoading" class="state-panel loading-state">
      正在加载设备详情，请稍候...
    </div>

    <div v-else-if="deviceError" :class="['state-panel', isNotFound ? 'empty-state' : 'error-state']">
      <h3>{{ isNotFound ? '未找到对应设备' : '设备详情加载失败' }}</h3>
      <p>{{ deviceError }}</p>
      <p class="subtle-text">
        {{ isNotFound ? '请返回设备台账重新选择设备。' : '可返回列表后重试，或检查后端服务状态。' }}
      </p>
      <div class="action-bar">
        <RouterLink :to="backToList" class="primary-link">返回设备台账</RouterLink>
      </div>
    </div>

    <template v-else-if="device">
      <section class="device-hero" aria-label="设备摘要">
        <div class="device-hero__identity">
          <div class="device-hero__avatar" aria-hidden="true">
            ATP
          </div>
          <div class="device-hero__title">
            <p class="section-tag">设备详情工作台</p>
            <h2>
              <span>{{ deviceDisplayCode }}</span>
              <em></em>
              <span>{{ displayValue(device.device_name) }}</span>
            </h2>
            <div class="device-hero__meta">
              <span>{{ displayValue(device.device_type) }}</span>
              <span>{{ displayValue(device.car_no) }}</span>
              <span>{{ displayValue(device.train_no) }}</span>
            </div>
          </div>
        </div>

        <div class="device-hero__status">
          <div class="device-status-unit">
            <span>当前状态</span>
            <strong :class="['status-dot-text', `status-dot-text--${currentStatusMeta.tone}`]">
              {{ currentStatusMeta.label }}
            </strong>
          </div>
          <div class="device-status-unit">
            <span>台账状态</span>
            <strong :class="['status-dot-text', `status-dot-text--${ledgerStatusMeta.tone}`]">
              {{ ledgerStatusMeta.label }}
            </strong>
          </div>
        </div>

        <div class="device-hero__actions">
          <RouterLink v-if="canManageDevice" :to="editInLedgerRoute" class="primary-link">编辑设备</RouterLink>
          <RouterLink :to="backToList" class="secondary-link">返回台账</RouterLink>
          <button type="button" class="secondary-button hero-action-button" @click="goToBusiness('alerts')">
            查看全部告警
          </button>
        </div>
      </section>

      <div class="device-workbench">
        <aside class="device-archive-panel" aria-label="设备档案">
          <header class="panel-header">
            <div>
              <p class="section-tag">设备档案</p>
              <h3>主数据与台账信息</h3>
            </div>
          </header>

          <section class="archive-group">
            <h4>基础信息</h4>
            <dl class="archive-list">
              <div v-for="item in basicArchiveFields" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value }}</dd>
              </div>
            </dl>
          </section>

          <section class="archive-group">
            <h4>台账信息</h4>
            <dl class="archive-list">
              <div>
                <dt>台账状态</dt>
                <dd>
                  <span :class="['mini-status', `mini-status--${ledgerStatusMeta.tone}`]">
                    {{ ledgerStatusMeta.label }}
                  </span>
                </dd>
              </div>
              <div v-for="item in ledgerArchiveFields" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value }}</dd>
              </div>
            </dl>
          </section>
        </aside>

        <main class="device-main-panel">
          <section class="work-panel status-overview-panel" aria-label="运行状态总览">
            <header class="panel-header">
              <div>
                <p class="section-tag">运行状态总览</p>
                <h3>实时口径与最新预测摘要</h3>
              </div>
              <span :class="['status-pill', `status-pill--${riskStatusMeta.tone}`]">
                {{ riskStatusMeta.label }}
              </span>
            </header>

            <div class="overview-kpi-row">
              <div v-for="item in overviewKpis" :key="item.key" class="overview-kpi">
                <span>{{ item.label }}</span>
                <strong :class="[`overview-kpi__value--${item.tone}`]">{{ item.value }}</strong>
                <small>{{ item.description }}</small>
              </div>
            </div>

            <div v-if="predictionLoading" class="inline-state">正在加载最新风险结果...</div>
            <div v-else-if="predictionError" class="inline-state inline-state--warning">
              最新风险结果加载失败：{{ predictionError }}
            </div>
            <div v-else-if="!latestPrediction" class="inline-state">暂无最新预测结果。</div>
          </section>

          <section class="work-panel recent-alert-panel" aria-label="最近告警">
            <header class="panel-header panel-header--compact">
              <div>
                <p class="section-tag">最近告警</p>
                <h3>最近告警（近3条）</h3>
              </div>
              <button type="button" class="link-button" @click="goToBusiness('alerts')">
                查看全部告警 &gt;
              </button>
            </header>

            <div v-if="alertsLoading" class="inline-state">正在加载最近告警记录...</div>
            <div v-else-if="alertsError" class="inline-state inline-state--warning">
              最近告警记录加载失败：{{ alertsError }}
            </div>
            <div v-else-if="recentAlerts.length === 0" class="empty-line-state">
              暂无告警记录
            </div>
            <div v-else class="alert-timeline">
              <article v-for="item in recentAlerts" :key="item.alert_id || item.alert_time" class="alert-timeline__item">
                <span :class="['alert-timeline__marker', alertLevelClass(item.alert_level)]" aria-hidden="true"></span>
                <div class="alert-timeline__body">
                  <div class="alert-timeline__head">
                    <strong>{{ displayValue(item.message) }}</strong>
                    <span>{{ formatDateTime(item.alert_time) }}</span>
                  </div>
                  <div class="alert-timeline__meta">
                    <span :class="['alert-badge', alertLevelClass(item.alert_level)]">
                      {{ formatAlertLevel(item.alert_level) }}
                    </span>
                    <span :class="['alert-badge', alertStatusClass(item.alert_status)]">
                      {{ formatAlertStatus(item.alert_status) }}
                    </span>
                    <span>{{ displayValue(item.alert_position) }}</span>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </main>
      </div>

      <section class="business-tabs-panel" aria-label="设备业务区域">
        <div class="business-tabs">
          <button
            v-for="tab in businessTabs"
            :key="tab.key"
            type="button"
            :class="['business-tab', { 'business-tab--active': activeBusinessTab === tab.key }]"
            @click="activeBusinessTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="business-tab-body">
          <section v-if="activeBusinessTab === 'monitor'" class="tab-workspace">
            <div>
              <h3>运行监测</h3>
              <p>查看该设备的运行监测数据、运行记录与监测曲线。</p>
            </div>
            <div class="tab-action-row">
              <button type="button" class="primary-button" @click="goToBusiness('monitor')">
                进入运行监测
              </button>
              <button type="button" class="secondary-button" @click="goToBusiness('run-records')">
                查看运行记录
              </button>
            </div>
          </section>

          <section v-else-if="activeBusinessTab === 'risk'" class="tab-workspace">
            <div>
              <h3>风险趋势</h3>
              <p>查看该设备最新风险分数、健康度、风险波动和预测时间。</p>
            </div>
            <div class="tab-metric-strip">
              <div v-for="item in riskSummaryFields" :key="item.label">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <div class="tab-action-row">
              <button type="button" class="primary-button" @click="goToBusiness('predictions')">
                查看风险预测
              </button>
            </div>
          </section>

          <section v-else-if="activeBusinessTab === 'alerts'" class="tab-workspace">
            <div>
              <h3>告警记录</h3>
              <p>查看该设备最近告警状态，并进入告警中心继续处置。</p>
            </div>
            <div v-if="recentAlerts.length === 0" class="empty-line-state">
              暂无告警记录
            </div>
            <div v-else class="compact-alert-list">
              <div v-for="item in recentAlerts" :key="`tab-${item.alert_id || item.alert_time}`" class="compact-alert-row">
                <span :class="['alert-badge', alertLevelClass(item.alert_level)]">
                  {{ formatAlertLevel(item.alert_level) }}
                </span>
                <strong>{{ displayValue(item.message) }}</strong>
                <span>{{ formatDateTime(item.alert_time) }}</span>
              </div>
            </div>
            <div class="tab-action-row">
              <button type="button" class="primary-button" @click="goToBusiness('alerts')">
                查看全部告警
              </button>
            </div>
          </section>

          <section v-else class="tab-workspace">
            <div>
              <h3>关联记录</h3>
              <p>围绕当前设备继续进入运行记录、风险预测和告警中心。</p>
            </div>
            <div class="related-entry-grid">
              <button type="button" class="related-entry" @click="goToBusiness('monitor')">
                <span>运行监测</span>
                <strong>运行记录与监测曲线</strong>
              </button>
              <button type="button" class="related-entry" @click="goToBusiness('predictions')">
                <span>风险预测</span>
                <strong>最新风险分析入口</strong>
              </button>
              <button type="button" class="related-entry" @click="goToBusiness('alerts')">
                <span>告警中心</span>
                <strong>告警记录与处置</strong>
              </button>
            </div>
          </section>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { getAlertList } from '../api/alert'
import { getDeviceDetail } from '../api/device'
import { getLatestPrediction } from '../api/prediction'
import { isAdmin } from '../utils/auth'
import { formatAlertLevel, formatAlertStatus, formatDeviceStatus, formatHealthScore, formatPercent } from '../utils/formatters'

const route = useRoute()
const router = useRouter()

const deviceLoading = ref(false)
const predictionLoading = ref(false)
const alertsLoading = ref(false)

const device = ref(null)
const latestPrediction = ref(null)
const recentAlerts = ref([])

const deviceError = ref('')
const predictionError = ref('')
const alertsError = ref('')
const isNotFound = ref(false)
const activeBusinessTab = ref('monitor')

let detailRequestId = 0

const routeDeviceId = computed(() => parseDeviceId(route.params.id))
const canManageDevice = computed(() => isAdmin())

const backToList = computed(() => ({
  name: 'devices',
  query: route.query
}))

const editInLedgerRoute = computed(() => ({
  name: 'devices',
  query: buildEditLedgerQuery()
}))

const deviceDisplayCode = computed(() =>
  displayValue(device.value?.device_code || device.value?.device_id || routeDeviceId.value)
)

const currentStatusMeta = computed(() =>
  getStatusMeta(
    device.value?.current_status ?? device.value?.device_status,
    device.value?.current_status_text || device.value?.device_status_text
  )
)

const ledgerStatusMeta = computed(() =>
  getStatusMeta(
    device.value?.ledger_status ?? device.value?.device_status,
    device.value?.ledger_status_text || device.value?.device_status_text
  )
)

const riskScore = computed(() => getRiskScore(latestPrediction.value))
const predictionTime = computed(() =>
  latestPrediction.value?.window_end_time || latestPrediction.value?.time || ''
)

const riskStatusMeta = computed(() => {
  if (predictionLoading.value) {
    return {
      label: '风险加载中',
      tone: 'muted'
    }
  }

  if (predictionError.value) {
    return {
      label: '风险待重试',
      tone: 'warning'
    }
  }

  if (!latestPrediction.value) {
    return {
      label: '暂无风险结果',
      tone: 'muted'
    }
  }

  const score = riskScore.value
  if (score !== null && score >= 0.75) {
    return {
      label: '高风险',
      tone: 'danger'
    }
  }

  if (score !== null && score >= 0.4) {
    return {
      label: '需关注',
      tone: 'warning'
    }
  }

  return {
    label: '风险可控',
    tone: 'success'
  }
})

const basicArchiveFields = computed(() => [
  {
    label: '设备ID',
    value: displayValue(device.value?.device_id)
  },
  {
    label: '设备编号',
    value: displayValue(device.value?.device_code)
  },
  {
    label: '设备名称',
    value: displayValue(device.value?.device_name)
  },
  {
    label: '设备类型',
    value: displayValue(device.value?.device_type)
  },
  {
    label: '车号',
    value: displayValue(device.value?.car_no)
  },
  {
    label: '车组号',
    value: displayValue(device.value?.train_no)
  },
  {
    label: 'ATP 类型',
    value: displayValue(device.value?.atp_type)
  },
  {
    label: '配属铁路局',
    value: displayValue(device.value?.attach_bureau)
  }
])

const ledgerArchiveFields = computed(() => [
  {
    label: '创建时间',
    value: formatDateTime(device.value?.create_time)
  },
  {
    label: '更新时间',
    value: formatDateTime(device.value?.update_time)
  }
])

const overviewKpis = computed(() => [
  {
    key: 'current-status',
    label: '当前状态',
    value: currentStatusMeta.value.label,
    tone: currentStatusMeta.value.tone,
    description: device.value?.status_source ? `来源：${device.value.status_source}` : '设备运行口径'
  },
  {
    key: 'risk-score',
    label: '最新风险分数',
    value: predictionMetric(formatPercent(riskScore.value, 2, '-')),
    tone: riskStatusMeta.value.tone,
    description: latestPrediction.value ? '来自最新预测结果' : '暂无结果'
  },
  {
    key: 'health-score',
    label: '健康度',
    value: predictionMetric(formatHealthScore(latestPrediction.value?.health_score, 2, '-')),
    tone: getHealthTone(latestPrediction.value?.health_score),
    description: latestPrediction.value ? '健康度评分' : '暂无结果'
  },
  {
    key: 'risk-std',
    label: '风险波动',
    value: predictionMetric(formatPercent(latestPrediction.value?.risk_std, 2, '-')),
    tone: getRiskStdTone(latestPrediction.value?.risk_std),
    description: latestPrediction.value ? '预测波动标准差' : '暂无结果'
  },
  {
    key: 'prediction-time',
    label: '最新预测时间',
    value: predictionMetric(formatDateTime(predictionTime.value)),
    tone: latestPrediction.value ? 'default' : 'muted',
    description: '预测窗口结束时间'
  }
])

const riskSummaryFields = computed(() => [
  {
    label: '最新风险分数',
    value: predictionMetric(formatPercent(riskScore.value, 2, '-'))
  },
  {
    label: '健康度',
    value: predictionMetric(formatHealthScore(latestPrediction.value?.health_score, 2, '-'))
  },
  {
    label: '风险波动',
    value: predictionMetric(formatPercent(latestPrediction.value?.risk_std, 2, '-'))
  },
  {
    label: '最新预测时间',
    value: predictionMetric(formatDateTime(predictionTime.value))
  }
])

const businessTabs = [
  {
    key: 'monitor',
    label: '运行监测'
  },
  {
    key: 'risk',
    label: '风险趋势'
  },
  {
    key: 'alerts',
    label: '告警记录'
  },
  {
    key: 'related',
    label: '关联记录'
  }
]

watch(
  () => route.params.id,
  () => {
    loadDeviceDetail()
  },
  {
    immediate: true
  }
)

async function loadDeviceDetail() {
  const requestId = ++detailRequestId
  const deviceId = routeDeviceId.value

  resetPageState()

  if (deviceId === null) {
    isNotFound.value = true
    deviceError.value = `设备 ID ${displayValue(route.params.id)} 不合法，请返回设备台账重新选择。`
    return
  }

  deviceLoading.value = true

  try {
    const result = await getDeviceDetail(deviceId)

    if (requestId !== detailRequestId) {
      return
    }

    const normalizedDevice = normalizeDevice(result)

    if (!normalizedDevice) {
      isNotFound.value = true
      deviceError.value = `未找到设备 ID 为 ${deviceId} 的台账记录。`
      return
    }

    device.value = normalizedDevice
  } catch (error) {
    if (requestId !== detailRequestId) {
      return
    }

    isNotFound.value = isNotFoundError(error)
    deviceError.value = isNotFound.value
      ? `未找到设备 ID 为 ${deviceId} 的台账记录。`
      : error.message || '设备详情加载失败'
  } finally {
    if (requestId === detailRequestId) {
      deviceLoading.value = false
    }
  }

  if (requestId === detailRequestId && device.value) {
    loadAuxiliaryData(deviceId, requestId)
  }
}

function loadAuxiliaryData(deviceId, requestId) {
  const deviceKey = device.value?.device_code || deviceId
  loadLatestPrediction(deviceKey, requestId)
  loadRecentAlerts(deviceKey, requestId)
}

async function loadLatestPrediction(deviceId, requestId) {
  predictionLoading.value = true
  predictionError.value = ''
  latestPrediction.value = null

  try {
    const result = await getLatestPrediction({ device_id: deviceId })

    if (requestId !== detailRequestId) {
      return
    }

    latestPrediction.value = normalizeLatestPrediction(result)
  } catch (error) {
    if (requestId !== detailRequestId) {
      return
    }

    predictionError.value = error.message || '最新风险结果加载失败'
    latestPrediction.value = null
  } finally {
    if (requestId === detailRequestId) {
      predictionLoading.value = false
    }
  }
}

async function loadRecentAlerts(deviceId, requestId) {
  alertsLoading.value = true
  alertsError.value = ''
  recentAlerts.value = []

  try {
    const result = await getAlertList({
      device_id: deviceId,
      page: 1,
      size: 3
    })

    if (requestId !== detailRequestId) {
      return
    }

    recentAlerts.value = normalizeAlertPage(result).slice(0, 3)
  } catch (error) {
    if (requestId !== detailRequestId) {
      return
    }

    alertsError.value = error.message || '最近告警记录加载失败'
    recentAlerts.value = []
  } finally {
    if (requestId === detailRequestId) {
      alertsLoading.value = false
    }
  }
}

function resetPageState() {
  deviceLoading.value = false
  predictionLoading.value = false
  alertsLoading.value = false
  device.value = null
  latestPrediction.value = null
  recentAlerts.value = []
  deviceError.value = ''
  predictionError.value = ''
  alertsError.value = ''
  isNotFound.value = false
}

function goToBusiness(name) {
  if (routeDeviceId.value === null) {
    return
  }

  const deviceCode = String(device.value?.device_code || routeDeviceId.value)

  router.push({
    name,
    query: {
      device_code: deviceCode
    }
  })
}

function buildEditLedgerQuery() {
  const deviceCode = String(device.value?.device_code || '').trim()

  if (deviceCode) {
    return {
      device_code: deviceCode,
      action: 'edit'
    }
  }

  return {
    device_id: String(routeDeviceId.value || ''),
    action: 'edit'
  }
}

function displayValue(value) {
  if (value === null || value === undefined) {
    return '-'
  }

  if (typeof value === 'string' && value.trim() === '') {
    return '-'
  }

  return String(value)
}

function predictionMetric(value) {
  if (predictionLoading.value) {
    return '加载中'
  }

  if (!latestPrediction.value) {
    return value === '-' ? '暂无结果' : value
  }

  return value
}

function getRiskScore(record) {
  const primaryValue = toFiniteNumber(record?.risk_score)
  if (primaryValue !== null) {
    return primaryValue
  }

  return toFiniteNumber(record?.calibrated_risk_score)
}

function formatDateTime(value) {
  const text = displayValue(value)

  if (text === '-') {
    return text
  }

  return text.replace('T', ' ').slice(0, 19)
}

function normalizeDevice(result) {
  const payload = unwrapData(result)

  if (!payload || typeof payload !== 'object') {
    return null
  }

  return {
    device_id: payload.device_id ?? '',
    device_code: payload.device_code ?? '',
    device_name: payload.device_name ?? '',
    device_type: payload.device_type ?? '',
    car_no: payload.car_no ?? '',
    train_no: payload.train_no ?? '',
    atp_type: payload.atp_type ?? '',
    attach_bureau: payload.attach_bureau ?? '',
    device_status: payload.device_status ?? '',
    device_status_text: payload.device_status_text ?? payload.status_text ?? '',
    ledger_status: payload.ledger_status ?? '',
    ledger_status_text: payload.ledger_status_text ?? '',
    current_status: payload.current_status ?? '',
    current_status_text: payload.current_status_text ?? '',
    status_source: payload.status_source ?? '',
    create_time: payload.create_time ?? '',
    update_time: payload.update_time ?? ''
  }
}

function normalizeLatestPrediction(result) {
  const payload = unwrapData(result)

  if (!payload || typeof payload !== 'object') {
    return null
  }

  return {
    device_id: payload.device_id ?? '',
    risk_score: getRiskScore(payload),
    calibrated_risk_score: toFiniteNumber(payload.calibrated_risk_score),
    health_score: toFiniteNumber(payload.health_score),
    risk_std: toFiniteNumber(payload.risk_std),
    window_end_time: payload.window_end_time ?? '',
    time: payload.time ?? ''
  }
}

function normalizeAlertPage(result) {
  const source = unwrapData(result)

  if (Array.isArray(source)) {
    return source.map((item) => normalizeAlertRecord(item))
  }

  if (!source || typeof source !== 'object') {
    return []
  }

  const candidates = [source.items, source.records, source.list, source.rows, source.data]
  const records = candidates.find((item) => Array.isArray(item)) || []

  return records.map((item) => normalizeAlertRecord(item))
}

function normalizeAlertRecord(record) {
  const source = record && typeof record === 'object' ? record : {}

  return {
    alert_id: source.alert_id ?? '',
    device_code: source.device_code ?? '',
    alert_level: source.alert_level ?? '',
    alert_status: source.alert_status ?? '',
    alert_time: source.alert_time ?? source.created_at ?? source.updated_at ?? '',
    alert_position: source.alert_position ?? source.position ?? '',
    message: source.alert_message ?? source.message ?? ''
  }
}

function unwrapData(result) {
  if (!result || typeof result !== 'object') {
    return result ?? null
  }

  if ('data' in result) {
    return result.data
  }

  return result
}

function getStatusMeta(status, text) {
  const label = displayValue(text) !== '-' ? displayValue(text) : formatDeviceStatus(status)

  return {
    label,
    tone: getStatusTone(status, label)
  }
}

function getStatusTone(status, label = '') {
  const numericStatus = Number(status)
  if (numericStatus === 1) {
    return 'success'
  }

  if (numericStatus === 2 || numericStatus === 3) {
    return 'warning'
  }

  if (numericStatus === 4) {
    return 'danger'
  }

  const normalizedLabel = String(label || '').trim()
  if (/正常|在用|启用|运行/.test(normalizedLabel)) {
    return 'success'
  }

  if (/关注|预警|待/.test(normalizedLabel)) {
    return 'warning'
  }

  if (/告警|严重|故障|停用|离线|异常/.test(normalizedLabel)) {
    return 'danger'
  }

  return 'muted'
}

function getHealthTone(value) {
  const score = toFiniteNumber(value)
  if (score === null) {
    return 'muted'
  }

  if (score <= 30) {
    return 'danger'
  }

  if (score <= 70) {
    return 'warning'
  }

  return 'success'
}

function getRiskStdTone(value) {
  const score = toFiniteNumber(value)
  if (score === null) {
    return 'muted'
  }

  if (score >= 0.2) {
    return 'warning'
  }

  return 'success'
}

function alertLevelClass(level) {
  const normalizedLevel = String(level || '').toLowerCase()

  if (normalizedLevel === 'high' || normalizedLevel === 'critical') {
    return 'alert-badge--high'
  }

  if (normalizedLevel === 'medium' || normalizedLevel === 'warning') {
    return 'alert-badge--medium'
  }

  if (normalizedLevel === 'low' || normalizedLevel === 'info') {
    return 'alert-badge--low'
  }

  return 'alert-badge--muted'
}

function alertStatusClass(status) {
  const normalizedStatus = String(status || '').toLowerCase()

  if (normalizedStatus === 'pending' || normalizedStatus === 'unhandled') {
    return 'alert-badge--pending'
  }

  if (normalizedStatus === 'processing') {
    return 'alert-badge--processing'
  }

  if (normalizedStatus === 'resolved') {
    return 'alert-badge--resolved'
  }

  return 'alert-badge--muted'
}

function parseDeviceId(value) {
  const normalizedValue = Array.isArray(value) ? value[0] : value
  const text = String(normalizedValue ?? '').trim()
  const parsedValue = Number(text)

  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const normalizedValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(normalizedValue) ? normalizedValue : null
}

function isNotFoundError(error) {
  return (
    error?.response?.status === 404 ||
    error?.payload?.code === 404 ||
    error?.response?.data?.code === 404
  )
}
</script>

<style scoped>
.device-detail-page {
  display: grid;
  gap: 18px;
}

.device-hero,
.device-archive-panel,
.work-panel,
.business-tabs-panel {
  border: 1px solid rgba(29, 79, 145, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 255, 0.92));
  box-shadow: 0 10px 28px rgba(16, 24, 40, 0.06);
}

.device-hero {
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(280px, 0.48fr) auto;
  gap: 24px;
  align-items: center;
  min-height: 118px;
  padding: 22px 24px;
  border-radius: 8px;
  overflow: hidden;
}

.device-hero__identity {
  display: flex;
  gap: 18px;
  align-items: center;
  min-width: 0;
}

.device-hero__avatar {
  display: grid;
  place-items: center;
  width: 72px;
  height: 72px;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1px solid rgba(29, 79, 145, 0.18);
  background: linear-gradient(135deg, #eaf3ff, #ffffff);
  color: var(--rail-brand);
  font-weight: 850;
  letter-spacing: 0;
  box-shadow: inset 0 0 0 8px rgba(29, 79, 145, 0.05);
}

.device-hero__title {
  min-width: 0;
}

.device-hero__title h2 {
  display: flex;
  gap: 14px;
  align-items: center;
  min-width: 0;
  margin: 6px 0 10px;
  color: var(--rail-text-strong);
  font-size: 1.55rem;
  line-height: 1.25;
}

.device-hero__title h2 span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.device-hero__title h2 em {
  width: 1px;
  height: 24px;
  flex: 0 0 auto;
  background: rgba(29, 79, 145, 0.22);
}

.device-hero__meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--rail-text-muted);
  font-size: 0.94rem;
}

.device-hero__meta span + span {
  padding-left: 14px;
  border-left: 1px solid rgba(29, 79, 145, 0.16);
}

.device-hero__status {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-left: 1px solid rgba(29, 79, 145, 0.12);
  border-right: 1px solid rgba(29, 79, 145, 0.12);
}

.device-status-unit {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 6px 20px;
}

.device-status-unit + .device-status-unit {
  border-left: 1px solid rgba(29, 79, 145, 0.12);
}

.device-status-unit span {
  color: var(--rail-text-muted);
  font-size: 0.84rem;
  font-weight: 700;
}

.device-hero__actions,
.tab-action-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
}

.hero-action-button {
  min-height: 38px;
}

.status-dot-text,
.mini-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: var(--rail-text-strong);
  font-size: 0.96rem;
  font-weight: 800;
}

.status-dot-text::before,
.mini-status::before {
  content: '';
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--rail-text-subtle);
  box-shadow: 0 0 0 4px rgba(102, 112, 133, 0.12);
}

.status-dot-text--success,
.mini-status--success {
  color: var(--rail-green);
}

.status-dot-text--success::before,
.mini-status--success::before {
  background: var(--rail-green);
  box-shadow: 0 0 0 4px var(--rail-green-soft);
}

.status-dot-text--warning,
.mini-status--warning {
  color: var(--rail-amber);
}

.status-dot-text--warning::before,
.mini-status--warning::before {
  background: var(--rail-amber);
  box-shadow: 0 0 0 4px var(--rail-amber-soft);
}

.status-dot-text--danger,
.mini-status--danger {
  color: var(--rail-red);
}

.status-dot-text--danger::before,
.mini-status--danger::before {
  background: var(--rail-red);
  box-shadow: 0 0 0 4px var(--rail-red-soft);
}

.device-workbench {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.device-archive-panel,
.work-panel,
.business-tabs-panel {
  border-radius: 8px;
}

.device-archive-panel {
  display: grid;
  gap: 18px;
  padding: 18px 20px;
}

.panel-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(29, 79, 145, 0.1);
}

.panel-header--compact {
  padding-bottom: 12px;
}

.panel-header h3,
.archive-group h4,
.tab-workspace h3 {
  margin: 0;
  color: var(--rail-text-strong);
}

.panel-header h3 {
  margin-top: 6px;
  font-size: 1.04rem;
}

.archive-group {
  display: grid;
  gap: 10px;
}

.archive-group + .archive-group {
  padding-top: 16px;
  border-top: 1px solid rgba(29, 79, 145, 0.12);
}

.archive-group h4 {
  position: relative;
  padding-left: 13px;
  font-size: 0.92rem;
}

.archive-group h4::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  width: 4px;
  height: 14px;
  border-radius: 3px;
  background: var(--rail-brand);
}

.archive-list {
  display: grid;
  margin: 0;
}

.archive-list div {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
  padding: 9px 0;
  border-bottom: 1px dashed rgba(29, 79, 145, 0.12);
}

.archive-list div:last-child {
  border-bottom: 0;
}

.archive-list dt,
.archive-list dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.archive-list dt {
  color: var(--rail-text-muted);
  font-size: 0.88rem;
}

.archive-list dd {
  color: var(--rail-text-strong);
  font-size: 0.9rem;
  font-weight: 700;
}

.device-main-panel {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.work-panel {
  display: grid;
  gap: 16px;
  min-width: 0;
  padding: 18px 20px;
}

.overview-kpi-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  min-width: 0;
}

.overview-kpi {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 4px 18px;
  border-left: 1px solid rgba(29, 79, 145, 0.12);
}

.overview-kpi:first-child {
  border-left: 0;
  padding-left: 0;
}

.overview-kpi span,
.overview-kpi small,
.alert-timeline__head span,
.alert-timeline__meta,
.tab-metric-strip span,
.related-entry span,
.compact-alert-row > span:last-child {
  color: var(--rail-text-muted);
  font-size: 0.84rem;
  font-weight: 700;
}

.overview-kpi strong {
  min-width: 0;
  color: var(--rail-text-strong);
  font-size: 1.28rem;
  line-height: 1.25;
  word-break: keep-all;
  overflow-wrap: normal;
}

.overview-kpi__value--success {
  color: var(--rail-green) !important;
}

.overview-kpi__value--warning {
  color: var(--rail-amber) !important;
}

.overview-kpi__value--danger {
  color: var(--rail-red) !important;
}

.overview-kpi__value--muted {
  color: var(--rail-text-muted) !important;
}

.inline-state,
.empty-line-state {
  padding: 12px 14px;
  border: 1px dashed rgba(29, 79, 145, 0.2);
  border-radius: 8px;
  background: rgba(29, 79, 145, 0.04);
  color: var(--rail-text-muted);
  font-weight: 700;
}

.inline-state--warning {
  border-color: rgba(181, 71, 8, 0.2);
  background: rgba(255, 247, 237, 0.8);
  color: var(--rail-amber);
}

.link-button {
  border: 0;
  background: transparent;
  color: var(--rail-brand);
  font: inherit;
  font-size: 0.9rem;
  font-weight: 800;
  cursor: pointer;
}

.link-button:hover {
  color: var(--rail-brand-strong);
}

.alert-timeline {
  display: grid;
  gap: 0;
}

.alert-timeline__item {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
  padding: 12px 0;
}

.alert-timeline__item + .alert-timeline__item {
  border-top: 1px solid rgba(29, 79, 145, 0.1);
}

.alert-timeline__marker {
  width: 9px;
  height: 9px;
  margin-top: 8px;
  border-radius: 50%;
  background: var(--rail-text-subtle);
  box-shadow: 0 0 0 4px rgba(102, 112, 133, 0.12);
}

.alert-timeline__marker.alert-badge--high {
  background: var(--rail-red);
  box-shadow: 0 0 0 4px var(--rail-red-soft);
}

.alert-timeline__marker.alert-badge--medium {
  background: var(--rail-amber);
  box-shadow: 0 0 0 4px var(--rail-amber-soft);
}

.alert-timeline__marker.alert-badge--low {
  background: var(--rail-green);
  box-shadow: 0 0 0 4px var(--rail-green-soft);
}

.alert-timeline__body {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.alert-timeline__head,
.alert-timeline__meta,
.compact-alert-row {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
}

.alert-timeline__head strong,
.compact-alert-row strong {
  min-width: 0;
  color: var(--rail-text-strong);
  font-size: 0.94rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-timeline__meta {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.alert-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: var(--rail-radius-pill);
  border: 1px solid transparent;
  font-size: 0.78rem;
  font-weight: 780;
  white-space: nowrap;
}

.alert-badge--high {
  color: #b42318;
  background: #fef3f2;
  border-color: #fecdca;
}

.alert-badge--medium,
.alert-badge--processing {
  color: #b54708;
  background: #fff7ed;
  border-color: #fed7aa;
}

.alert-badge--low,
.alert-badge--resolved {
  color: #027a48;
  background: #ecfdf3;
  border-color: #abefc6;
}

.alert-badge--pending {
  color: #1d4f91;
  background: #eef4ff;
  border-color: #c7d7fe;
}

.alert-badge--muted {
  color: #5b6d86;
  background: #f5f7fa;
  border-color: #d7e1ee;
}

.business-tabs-panel {
  overflow: hidden;
}

.business-tabs {
  display: flex;
  min-width: 0;
  padding: 0 20px;
  border-bottom: 1px solid rgba(29, 79, 145, 0.12);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.72), rgba(255, 255, 255, 0.8));
}

.business-tab {
  position: relative;
  min-height: 48px;
  padding: 0 26px;
  border: 0;
  background: transparent;
  color: var(--rail-text);
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.business-tab::after {
  content: '';
  position: absolute;
  left: 20px;
  right: 20px;
  bottom: 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: transparent;
}

.business-tab--active {
  color: var(--rail-brand);
}

.business-tab--active::after {
  background: var(--rail-brand);
}

.business-tab-body {
  padding: 22px 24px 24px;
}

.tab-workspace {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.tab-workspace p {
  margin: 8px 0 0;
  color: var(--rail-text-muted);
  line-height: 1.7;
}

.tab-action-row {
  justify-content: flex-start;
}

.tab-metric-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid rgba(29, 79, 145, 0.12);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.62);
}

.tab-metric-strip div {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 16px;
}

.tab-metric-strip div + div {
  border-left: 1px solid rgba(29, 79, 145, 0.12);
}

.tab-metric-strip strong {
  min-width: 0;
  color: var(--rail-text-strong);
  overflow-wrap: anywhere;
}

.compact-alert-list {
  display: grid;
  border: 1px solid rgba(29, 79, 145, 0.12);
  border-radius: 8px;
  overflow: hidden;
}

.compact-alert-row {
  justify-content: flex-start;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.62);
}

.compact-alert-row + .compact-alert-row {
  border-top: 1px solid rgba(29, 79, 145, 0.1);
}

.related-entry-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.related-entry {
  display: grid;
  gap: 8px;
  min-height: 92px;
  padding: 16px;
  border: 1px solid rgba(29, 79, 145, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}

.related-entry:hover {
  transform: translateY(-1px);
  border-color: var(--rail-brand);
  box-shadow: 0 10px 24px rgba(29, 79, 145, 0.12);
}

.related-entry strong {
  color: var(--rail-text-strong);
}

@media (max-width: 1280px) {
  .device-hero {
    grid-template-columns: 1fr;
  }

  .device-hero__status {
    border-right: 0;
  }

  .device-hero__actions {
    justify-content: flex-start;
  }

  .overview-kpi-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px 0;
  }

  .overview-kpi:nth-child(4) {
    border-left: 0;
    padding-left: 0;
  }
}

@media (max-width: 980px) {
  .device-workbench {
    grid-template-columns: 1fr;
  }

  .device-archive-panel {
    position: static;
  }

  .tab-metric-strip,
  .related-entry-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .device-hero,
  .device-archive-panel,
  .work-panel,
  .business-tab-body {
    padding: 18px;
  }

  .device-hero__identity,
  .panel-header,
  .alert-timeline__head {
    align-items: flex-start;
    flex-direction: column;
  }

  .device-hero__title h2 {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .device-hero__title h2 em,
  .device-hero__meta span + span {
    display: none;
  }

  .device-hero__status,
  .overview-kpi-row,
  .tab-metric-strip,
  .related-entry-grid {
    grid-template-columns: 1fr;
  }

  .device-status-unit,
  .overview-kpi,
  .overview-kpi:first-child,
  .overview-kpi:nth-child(4),
  .tab-metric-strip div {
    padding-left: 0;
    border-left: 0;
  }

  .device-status-unit + .device-status-unit,
  .tab-metric-strip div + div {
    padding-top: 14px;
    border-top: 1px solid rgba(29, 79, 145, 0.12);
  }

  .archive-list div {
    grid-template-columns: 84px minmax(0, 1fr);
  }

  .business-tabs {
    overflow-x: auto;
    padding: 0 12px;
  }

  .business-tab {
    flex: 0 0 auto;
    padding: 0 18px;
  }
}
</style>
