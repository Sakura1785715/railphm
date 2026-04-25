<template>
  <section class="device-detail-page">
    <div class="device-detail-topbar">
      <div class="device-detail-topbar__content">
        <p class="page-tag">设备详情</p>
        <h2>{{ deviceTitle }}</h2>
        <p class="page-description">
          展示设备基础信息、最新风险状态和最近告警记录，并提供相关业务页面快捷入口。
        </p>
      </div>

      <div class="device-detail-topbar__actions">
        <span :class="['status-pill', `status-pill--${topbarStatus.tone}`]">{{ topbarStatus.label }}</span>
        <span v-if="device" class="device-detail-topbar__chip">设备 ID {{ displayValue(device.device_id) }}</span>
        <RouterLink :to="backToList" class="secondary-link">返回设备台账</RouterLink>
      </div>
    </div>

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
      <article class="device-detail-card device-summary-card">
        <div class="device-detail-card__header">
          <div>
            <p class="section-tag">设备档案</p>
            <h3>台账主数据</h3>
          </div>
          <span :class="['status-pill', `status-pill--${deviceStatusMeta.tone}`]">
            {{ deviceStatusMeta.label }}
          </span>
        </div>

        <dl class="detail-list device-summary-grid">
          <div v-for="item in deviceFields" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </article>

      <div class="device-business-grid">
        <article class="device-detail-card device-risk-card">
          <div class="device-detail-card__header">
            <div>
              <p class="section-tag">最新风险状态</p>
              <h3>风险与健康度摘要</h3>
            </div>
            <span :class="['status-pill', `status-pill--${riskStatus.tone}`]">{{ riskStatus.label }}</span>
          </div>

          <div v-if="predictionLoading" class="state-panel loading-state device-section-state">
            正在加载最新风险结果...
          </div>

          <div v-else-if="predictionError" class="state-panel error-state device-section-state">
            最新风险结果加载失败：{{ predictionError }}
          </div>

          <div v-else-if="!latestPrediction" class="state-panel empty-state device-section-state">
            暂无风险结果
          </div>

          <template v-else>
            <div class="device-kpi-grid">
              <article class="device-kpi">
                <span>最新风险分数</span>
                <strong>{{ formatNumber(riskScore, 2) }}</strong>
              </article>
              <article class="device-kpi">
                <span>当前健康度</span>
                <strong>{{ formatNumber(latestPrediction.health_score, 1) }}</strong>
              </article>
              <article class="device-kpi">
                <span>风险波动</span>
                <strong>{{ formatNumber(latestPrediction.risk_std, 3) }}</strong>
              </article>
              <article class="device-kpi">
                <span>模型版本</span>
                <strong>{{ displayValue(latestPrediction.model_version) }}</strong>
              </article>
            </div>

            <dl class="device-window-list">
              <div>
                <dt>窗口开始时间</dt>
                <dd>{{ formatDateTime(latestPrediction.window_start_time) }}</dd>
              </div>
              <div>
                <dt>窗口结束时间</dt>
                <dd>{{ formatDateTime(latestPrediction.window_end_time) }}</dd>
              </div>
            </dl>
          </template>
        </article>

        <article class="device-detail-card device-alert-card">
          <div class="device-detail-card__header">
            <div>
              <p class="section-tag">最近告警记录</p>
              <h3>最近 3 条告警摘要</h3>
            </div>
            <button type="button" class="secondary-button" @click="goToBusiness('alerts')">
              查看全部告警
            </button>
          </div>

          <div v-if="alertsLoading" class="state-panel loading-state device-section-state">
            正在加载最近告警记录...
          </div>

          <div v-else-if="alertsError" class="state-panel error-state device-section-state">
            最近告警记录加载失败：{{ alertsError }}
          </div>

          <div v-else-if="recentAlerts.length === 0" class="state-panel empty-state device-section-state">
            暂无告警记录
          </div>

          <div v-else class="device-alert-list">
            <article v-for="item in recentAlerts" :key="item.alert_id || item.alert_time" class="device-alert-item">
              <div class="device-alert-item__top">
                <span class="device-alert-item__id">#{{ displayValue(item.alert_id) }}</span>
                <span :class="['alert-badge', getAlertLevelClass(item.alert_level)]">
                  {{ displayValue(item.alert_level) }}
                </span>
                <span :class="['alert-badge', getAlertStatusClass(item.alert_status)]">
                  {{ displayValue(item.alert_status) }}
                </span>
              </div>
              <p class="device-alert-item__message" :title="displayValue(item.message)">
                {{ displayValue(item.message) }}
              </p>
              <div class="device-alert-item__meta">
                <span>{{ formatDateTime(item.alert_time) }}</span>
                <span>{{ displayValue(item.alert_position) }}</span>
              </div>
            </article>
          </div>
        </article>
      </div>

      <article class="device-detail-card device-action-card">
        <div class="device-detail-card__header">
          <div>
            <p class="section-tag">快捷入口</p>
            <h3>围绕该设备继续查看</h3>
          </div>
          <span class="status-pill status-pill--default">自动携带 device_id</span>
        </div>

        <div class="quick-entry-grid">
          <button type="button" class="quick-entry-card" @click="goToBusiness('monitor')">
            <span class="status-pill status-pill--default">运行监测</span>
            <strong>查看运行监测</strong>
            <p>查看该设备的 ATP 监测曲线。</p>
          </button>

          <button type="button" class="quick-entry-card" @click="goToBusiness('predictions')">
            <span class="status-pill status-pill--default">风险预测</span>
            <strong>查看风险趋势</strong>
            <p>查看该设备的风险变化趋势。</p>
          </button>

          <button type="button" class="quick-entry-card" @click="goToBusiness('alerts')">
            <span class="status-pill status-pill--default">告警中心</span>
            <strong>查看告警记录</strong>
            <p>查看该设备的告警记录。</p>
          </button>
        </div>
      </article>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { getAlertList } from '../api/alert'
import { getDeviceDetail } from '../api/device'
import { getLatestPrediction } from '../api/prediction'

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

let detailRequestId = 0

const routeDeviceId = computed(() => parseDeviceId(route.params.id))

const backToList = computed(() => ({
  name: 'devices',
  query: route.query
}))

const deviceTitle = computed(() => {
  if (device.value) {
    return `ATP设备详情：${displayValue(device.value.car_no || device.value.device_id)}`
  }

  return routeDeviceId.value ? `设备 ${routeDeviceId.value}` : 'ATP设备详情'
})

const topbarStatus = computed(() => {
  if (deviceLoading.value) {
    return {
      label: '设备加载中',
      tone: 'muted'
    }
  }

  if (deviceError.value) {
    return {
      label: '详情待处理',
      tone: 'warning'
    }
  }

  return deviceStatusMeta.value
})

const deviceStatusMeta = computed(() => getDeviceStatusMeta(device.value?.device_status))

const deviceFields = computed(() => [
  {
    label: '设备ID',
    value: displayValue(device.value?.device_id)
  },
  {
    label: '车号',
    value: displayValue(device.value?.car_no)
  },
  {
    label: 'ATP 类型',
    value: displayValue(device.value?.atp_type)
  },
  {
    label: '配属铁路局',
    value: displayValue(device.value?.attach_bureau)
  },
  {
    label: '设备状态',
    value: deviceStatusMeta.value.label
  }
])

const riskScore = computed(() => getRiskScore(latestPrediction.value))

const riskStatus = computed(() => {
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

  const healthScore = toFiniteNumber(latestPrediction.value.health_score)

  if (healthScore !== null && healthScore <= 30) {
    return {
      label: '健康度偏低',
      tone: 'danger'
    }
  }

  if (healthScore !== null && healthScore <= 70) {
    return {
      label: '健康度需关注',
      tone: 'warning'
    }
  }

  return {
    label: '摘要已更新',
    tone: healthScore === null ? 'default' : 'success'
  }
})

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
  loadLatestPrediction(deviceId, requestId)
  loadRecentAlerts(deviceId, requestId)
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

  router.push({
    name,
    query: {
      device_id: String(routeDeviceId.value)
    }
  })
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

function getRiskScore(record) {
  const primaryValue = toFiniteNumber(record?.risk_score)
  if (primaryValue !== null) {
    return primaryValue
  }

  return toFiniteNumber(record?.calibrated_risk_score)
}

function formatNumber(value, digits) {
  const normalizedValue = toFiniteNumber(value)
  return normalizedValue === null ? '-' : normalizedValue.toFixed(digits)
}

function formatDateTime(value) {
  const text = displayValue(value)

  if (text === '-') {
    return text
  }

  return text.replace('T', ' ').slice(0, 16)
}

function normalizeDevice(result) {
  const payload = unwrapData(result)

  if (!payload || typeof payload !== 'object') {
    return null
  }

  return {
    device_id: payload.device_id ?? '',
    car_no: payload.car_no ?? '',
    atp_type: payload.atp_type ?? '',
    attach_bureau: payload.attach_bureau ?? '',
    device_status: payload.device_status ?? ''
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
    model_version: payload.model_version ?? '',
    window_start_time: payload.window_start_time ?? '',
    window_end_time: payload.window_end_time ?? ''
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
    alert_level: source.alert_level ?? '',
    alert_status: source.alert_status ?? '',
    alert_time: source.alert_time ?? '',
    alert_position: source.alert_position ?? '',
    message: source.message ?? ''
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

function getDeviceStatusMeta(status) {
  if (Number(status) === 1) {
    return {
      label: '在册运行',
      tone: 'success'
    }
  }

  if (Number(status) === 0) {
    return {
      label: '停用观察',
      tone: 'warning'
    }
  }

  return {
    label: '未知状态',
    tone: 'muted'
  }
}

function getAlertLevelClass(level) {
  const normalizedLevel = String(level || '').toUpperCase()

  if (normalizedLevel === 'HIGH') {
    return 'alert-badge--high'
  }

  if (normalizedLevel === 'MEDIUM') {
    return 'alert-badge--medium'
  }

  if (normalizedLevel === 'LOW') {
    return 'alert-badge--low'
  }

  return 'alert-badge--muted'
}

function getAlertStatusClass(status) {
  const normalizedStatus = String(status || '').toUpperCase()

  if (normalizedStatus === 'PENDING') {
    return 'alert-badge--pending'
  }

  if (normalizedStatus === 'PROCESSING') {
    return 'alert-badge--processing'
  }

  if (normalizedStatus === 'RESOLVED') {
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
  gap: 20px;
}

.device-detail-topbar,
.device-detail-topbar__actions,
.device-detail-card__header,
.device-alert-item__top,
.device-alert-item__meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.device-detail-topbar__actions {
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
}

.device-detail-topbar__chip {
  min-height: 36px;
}

.device-detail-card {
  display: grid;
  gap: 20px;
  padding: 24px 26px;
}

.device-detail-card__header h3 {
  margin: 8px 0 0;
}

.device-business-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.95fr);
  gap: 20px;
  align-items: start;
}

.device-summary-grid {
  margin-top: 0;
}

.device-kpi-grid,
.quick-entry-grid {
  display: grid;
  gap: 14px;
}

.device-kpi-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.device-kpi {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-lg);
  background: rgba(255, 255, 255, 0.62);
  box-shadow: var(--rail-shadow-sm);
}

.device-kpi span,
.device-window-list dt,
.device-alert-item__meta,
.device-alert-item__id {
  color: var(--rail-text-muted);
  font-size: 0.88rem;
  font-weight: 700;
}

.device-kpi strong,
.device-window-list dd {
  min-width: 0;
  color: var(--rail-text-strong);
  font-size: 1.06rem;
  font-weight: 780;
  overflow-wrap: anywhere;
}

.device-window-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin: 0;
}

.device-window-list div {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 16px;
  border-radius: var(--rail-radius-md);
  background: rgba(35, 95, 104, 0.06);
}

.device-window-list dd,
.device-window-list dt {
  margin: 0;
}

.device-section-state {
  margin: 0;
}

.device-alert-list {
  display: grid;
  gap: 12px;
}

.device-alert-item {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-md);
  background: rgba(255, 255, 255, 0.62);
}

.device-alert-item__top,
.device-alert-item__meta {
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 8px;
}

.device-alert-item__message {
  margin: 0;
  color: var(--rail-text-strong);
  line-height: 1.6;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow-wrap: anywhere;
}

.quick-entry-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.quick-entry-card {
  display: grid;
  gap: 12px;
  min-height: 148px;
  padding: 20px;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-lg);
  background: rgba(255, 255, 255, 0.68);
  box-shadow: var(--rail-shadow-sm);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.quick-entry-card:hover {
  transform: translateY(-1px);
  border-color: var(--rail-border-strong);
  box-shadow: var(--rail-shadow-lg);
}

.quick-entry-card strong {
  color: var(--rail-text-strong);
  font-size: 1.05rem;
}

.quick-entry-card p {
  margin: 0;
  color: var(--rail-text-muted);
  line-height: 1.7;
}

.alert-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: var(--rail-radius-pill);
  border: 1px solid transparent;
  font-size: 0.8rem;
  font-weight: 760;
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

@media (max-width: 1180px) {
  .device-business-grid,
  .device-kpi-grid,
  .quick-entry-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .device-detail-topbar,
  .device-detail-topbar__actions,
  .device-detail-card__header,
  .device-business-grid,
  .device-kpi-grid,
  .quick-entry-grid,
  .device-window-list {
    grid-template-columns: 1fr;
  }

  .device-detail-topbar,
  .device-detail-topbar__actions,
  .device-detail-card__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .device-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
