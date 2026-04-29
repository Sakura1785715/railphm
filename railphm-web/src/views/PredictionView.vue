<template>
  <section class="prediction-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">风险预测</p>
        <h2>设备故障风险趋势</h2>
        <p class="page-description">
          展示设备最新故障风险结果、历史风险变化趋势，并支持触发一次 mock 推理验证 AI 服务调用链路。
        </p>
      </div>

      <div class="monitor-topbar__meta">
        <span :class="['status-pill', `status-pill--${statusTone}`]">{{ statusLabel }}</span>
        <span class="monitor-topbar__summary">{{ statusDescription }}</span>
      </div>
    </div>

    <form class="monitor-filter-card" @submit.prevent="handleSearch">
      <div class="monitor-filter-card__header">
        <div>
          <h3>查询条件</h3>
          <p>默认参数用于匹配当前后端 mock 风险结果，可按设备编号和时间范围重新查询。</p>
        </div>
      </div>

      <div class="monitor-filter-grid prediction-filter-grid">
        <label class="filter-field">
          <span>设备编号</span>
          <input v-model.trim="filters.deviceId" type="text" placeholder="1" :disabled="queryLoading" />
        </label>

        <label class="filter-field">
          <span>开始时间</span>
          <input
            v-model.trim="filters.startTime"
            type="text"
            placeholder="2026-04-01 08:00:00"
            :disabled="queryLoading"
          />
        </label>

        <label class="filter-field">
          <span>结束时间</span>
          <input
            v-model.trim="filters.endTime"
            type="text"
            placeholder="2026-04-01 11:00:00"
            :disabled="queryLoading"
          />
        </label>
      </div>

      <div class="action-bar monitor-filter-card__actions">
        <button type="submit" class="primary-button" :disabled="queryLoading">
          {{ queryLoading ? '查询中...' : '查询风险结果' }}
        </button>
        <button type="button" class="secondary-button" :disabled="queryLoading" @click="handleReset">
          重置
        </button>
      </div>
    </form>

    <div v-if="validationMessage" class="state-panel error-state">
      {{ validationMessage }}
    </div>

    <div v-if="queryLoading && !hasPredictionData" class="state-panel loading-state">
      正在加载风险预测数据...
    </div>

    <div v-if="queryErrorMessage" class="state-panel error-state">
      风险预测数据加载失败：{{ queryErrorMessage }}
    </div>

    <section class="monitor-section prediction-panel">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">最新结果</p>
          <h3>最新风险结果卡片</h3>
        </div>
        <p>当前展示最新一次风险评估结果，健康度与告警等级以服务端返回的统一解释结果为准。</p>
      </div>

      <div class="prediction-panel__meta">
        <span class="device-chip">设备 ID {{ currentDeviceIdDisplay }}</span>
        <span :class="['status-pill', `status-pill--${latestRiskMeta.tone}`]">{{ latestRiskMeta.label }}</span>
      </div>

      <div
        v-if="!latestRecord && !queryLoading && !queryErrors.latest && hasLoaded"
        class="state-panel empty-state"
      >
        当前设备暂无最新风险结果。
      </div>

      <div
        v-else-if="latestRecord"
        class="monitor-overview-grid prediction-overview-grid"
      >
        <article class="monitor-overview-card">
          <span>设备编号</span>
          <strong>{{ displayText(latestRecord.device_id) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>风险分数</span>
          <strong>{{ formatNumber(latestRecord.risk_score, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>健康度</span>
          <strong>{{ formatNumber(latestRecord.health_score, 1) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>风险波动</span>
          <strong>{{ formatNumber(latestRecord.risk_std, 3) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>模型版本</span>
          <strong>{{ displayText(latestRecord.model_version) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>窗口开始时间</span>
          <strong>{{ displayText(latestRecord.window_start_time) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>窗口结束时间</span>
          <strong>{{ displayText(latestRecord.window_end_time) }}</strong>
        </article>
      </div>
    </section>

    <div v-if="historyEmptyMessage" class="state-panel empty-state">
      {{ historyEmptyMessage }}
    </div>

    <section class="monitor-section prediction-panel">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">趋势图</p>
          <h3>风险趋势与健康度趋势</h3>
        </div>
        <p>历史数据按时间升序绘制，横轴优先使用 `window_end_time`，仅展示后端已返回的历史结果。</p>
      </div>

      <div class="prediction-chart-grid">
        <MetricTrendChart
          title="风险趋势折线图"
          description="展示指定设备在查询时间范围内的风险分数变化，不自动追加 mock 推理结果。"
          metric-name="风险分数"
          :points="riskTrendPoints"
          :loading="queryLoading"
          :error="queryErrors.history"
          height="320px"
        />

        <MetricTrendChart
          title="健康度趋势折线图"
          description="展示指定设备在查询时间范围内的健康度变化，帮助观察状态稳定性。"
          metric-name="健康度"
          unit=""
          :points="healthTrendPoints"
          :loading="queryLoading"
          :error="queryErrors.history"
          height="320px"
        />
      </div>
    </section>

    <section class="prediction-infer-card">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">Mock 推理</p>
          <h3>触发一次 mock 推理</h3>
        </div>
        <p>当前结果仅用于演示 `railphm-web -> railphm-server -> railphm-ai` 调用链路，不写入历史趋势。</p>
      </div>

      <form class="prediction-infer-form" @submit.prevent="handleInfer">
        <div class="prediction-infer-grid">
          <label class="filter-field">
            <span>设备编号</span>
            <input v-model.trim="inferForm.deviceId" type="text" placeholder="1" :disabled="inferLoading" />
          </label>

          <label class="filter-field">
            <span>ts_end</span>
            <input
              v-model.trim="inferForm.tsEnd"
              type="text"
              placeholder="2026-04-01 10:05:00"
              :disabled="inferLoading"
            />
          </label>

          <label class="filter-field">
            <span>window_minutes</span>
            <input
              v-model.trim="inferForm.windowMinutes"
              type="text"
              placeholder="5"
              :disabled="inferLoading"
            />
          </label>
        </div>

        <div class="action-bar prediction-infer-form__actions">
          <button type="submit" class="primary-button" :disabled="inferLoading">
            {{ inferLoading ? '推理中...' : '触发一次 mock 推理' }}
          </button>
        </div>
      </form>

      <div v-if="inferLoading" class="state-panel loading-state">
        正在触发 mock 推理...
      </div>

      <div v-if="inferError" class="state-panel error-state">
        {{ inferError }}
      </div>

      <div v-if="!inferLoading && !inferError && !inferResult" class="state-panel empty-state">
        当前尚未触发 mock 推理，点击按钮后将在此处展示本次推理结果。
      </div>

      <div v-else-if="inferResult" class="prediction-infer-result">
        <div class="prediction-panel__meta">
          <span class="device-chip">设备 ID {{ displayText(inferResult.device_id) }}</span>
          <span :class="['status-pill', `status-pill--${inferAlertMeta.tone}`]">{{ inferAlertMeta.label }}</span>
          <span class="status-pill status-pill--default">{{ displayText(inferResult.condition_label) }}</span>
        </div>

        <div class="monitor-overview-grid prediction-overview-grid">
          <article class="monitor-overview-card">
            <span>风险分数</span>
            <strong>{{ formatNumber(inferResult.risk_score, 2) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>健康度</span>
            <strong>{{ formatNumber(inferResult.health_score, 1) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>alert_level</span>
            <strong>{{ displayText(inferResult.alert_level) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>风险波动</span>
            <strong>{{ formatNumber(inferResult.risk_std, 3) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>condition_label</span>
            <strong>{{ displayText(inferResult.condition_label) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>模型版本</span>
            <strong>{{ displayText(inferResult.model_version) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>窗口开始时间</span>
            <strong>{{ displayText(inferResult.window_start_time) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>窗口结束时间</span>
            <strong>{{ displayText(inferResult.window_end_time) }}</strong>
          </article>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { MetricTrendChart } from '../components/chart'
import {
  getLatestPrediction,
  getPredictionHistory,
  inferPrediction
} from '../api/prediction'
import { getRiskLevelMeta } from '../utils/dashboard'

const route = useRoute()

const DEFAULT_FILTERS = {
  deviceId: '1',
  startTime: '2026-04-01 08:00:00',
  endTime: '2026-04-01 11:00:00'
}

const DEFAULT_INFER_FORM = {
  deviceId: DEFAULT_FILTERS.deviceId,
  tsEnd: '2026-04-01 10:05:00',
  windowMinutes: '5'
}

const queryDeviceId = normalizeQueryDeviceId(route.query.device_id)
const filters = reactive({
  ...DEFAULT_FILTERS,
  deviceId: queryDeviceId || DEFAULT_FILTERS.deviceId
})
const inferForm = reactive({
  ...DEFAULT_INFER_FORM,
  deviceId: filters.deviceId
})

const queryLoading = ref(false)
const validationMessage = ref('')
const hasLoaded = ref(false)
const latestRecord = ref(null)
const historyRecords = ref([])
const historyMeta = ref({
  device_id: DEFAULT_FILTERS.deviceId,
  start_time: DEFAULT_FILTERS.startTime,
  end_time: DEFAULT_FILTERS.endTime
})
const queryErrors = reactive({
  latest: '',
  history: ''
})

const inferLoading = ref(false)
const inferError = ref('')
const inferResult = ref(null)

const hasPredictionData = computed(() => Boolean(latestRecord.value) || historyRecords.value.length > 0)
const latestRiskMeta = computed(() => getRiskLevelMeta(latestRecord.value?.health_score))
const currentDeviceIdDisplay = computed(
  () => displayText(latestRecord.value?.device_id ?? historyMeta.value.device_id ?? filters.deviceId)
)

const queryErrorMessage = computed(() =>
  [
    queryErrors.latest ? `最新结果：${queryErrors.latest}` : '',
    queryErrors.history ? `历史趋势：${queryErrors.history}` : ''
  ]
    .filter(Boolean)
    .join('；')
)

const historyEmptyMessage = computed(() => {
  if (!hasLoaded.value || queryLoading.value || queryErrors.history) {
    return ''
  }

  return historyRecords.value.length === 0 ? '当前时间范围内暂无历史风险趋势数据。' : ''
})

const riskTrendPoints = computed(() =>
  historyRecords.value.map((item) => ({
    time: getRecordTime(item),
    value: item.risk_score
  }))
)

const healthTrendPoints = computed(() =>
  historyRecords.value.map((item) => ({
    time: getRecordTime(item),
    value: item.health_score
  }))
)

const statusTone = computed(() => {
  if (queryLoading.value) {
    return 'muted'
  }

  if (validationMessage.value || queryErrors.latest || queryErrors.history) {
    return 'warning'
  }

  if (hasPredictionData.value) {
    return 'success'
  }

  return 'default'
})

const statusLabel = computed(() => {
  if (queryLoading.value) {
    return '风险数据加载中'
  }

  if (validationMessage.value || queryErrors.latest || queryErrors.history) {
    return '查询待处理'
  }

  if (hasPredictionData.value) {
    return '风险结果已接入'
  }

  return '等待查询'
})

const statusDescription = computed(() => {
  if (queryLoading.value) {
    return '正在请求 /api/v1/predictions/latest 与 /api/v1/predictions/history'
  }

  if (queryErrors.latest || queryErrors.history) {
    return '部分接口请求失败，可检查后端与 AI 服务状态后重试'
  }

  if (validationMessage.value) {
    return '请补齐设备编号与时间范围'
  }

  if (hasPredictionData.value) {
    return `当前设备 ${currentDeviceIdDisplay.value} 已返回 ${historyRecords.value.length} 个历史点位`
  }

  return '按设备编号与时间范围查看风险趋势与健康度趋势'
})

const inferAlertMeta = computed(() => {
  const alertLevel = inferResult.value?.alert_level

  if (alertLevel === 'HIGH') {
    return {
      label: '高等级预警',
      tone: 'danger'
    }
  }

  if (alertLevel === 'MEDIUM') {
    return {
      label: '中等级关注',
      tone: 'warning'
    }
  }

  if (alertLevel === 'LOW') {
    return {
      label: '低等级提示',
      tone: 'success'
    }
  }

  return {
    label: '结果待解释',
    tone: 'default'
  }
})

watch(
  () => filters.deviceId,
  (deviceId) => {
    inferForm.deviceId = deviceId || DEFAULT_FILTERS.deviceId
  }
)

onMounted(() => {
  fetchPredictionData()
})

async function fetchPredictionData() {
  const message = validateFilters()

  if (message) {
    validationMessage.value = message
    latestRecord.value = null
    historyRecords.value = []
    queryErrors.latest = ''
    queryErrors.history = ''
    return
  }

  queryLoading.value = true
  validationMessage.value = ''
  queryErrors.latest = ''
  queryErrors.history = ''

  const params = buildQueryParams()
  historyMeta.value = {
    device_id: params.device_id,
    start_time: params.start_time,
    end_time: params.end_time
  }

  try {
    const [latestResult, historyResult] = await Promise.allSettled([
      getLatestPrediction({ device_id: params.device_id }),
      getPredictionHistory(params)
    ])

    if (latestResult.status === 'fulfilled') {
      latestRecord.value = normalizeLatest(normalizePayload(latestResult.value))
    } else {
      latestRecord.value = null
      queryErrors.latest = latestResult.reason?.message || '最新风险结果加载失败'
    }

    if (historyResult.status === 'fulfilled') {
      const payload = normalizePayload(historyResult.value)

      historyMeta.value = {
        device_id: payload?.device_id ?? params.device_id,
        start_time: payload?.start_time || params.start_time,
        end_time: payload?.end_time || params.end_time
      }
      historyRecords.value = normalizeHistory(payload)
    } else {
      historyRecords.value = []
      queryErrors.history = historyResult.reason?.message || '历史趋势加载失败'
    }
  } finally {
    hasLoaded.value = true
    queryLoading.value = false
  }
}

async function handleSearch() {
  await fetchPredictionData()
}

async function handleReset() {
  Object.assign(filters, DEFAULT_FILTERS)
  Object.assign(inferForm, DEFAULT_INFER_FORM)
  inferError.value = ''
  inferResult.value = null
  await fetchPredictionData()
}

async function handleInfer() {
  const message = validateInferForm()

  if (message) {
    inferError.value = message
    inferResult.value = null
    return
  }

  inferLoading.value = true
  inferError.value = ''
  inferResult.value = null

  try {
    const result = await inferPrediction(buildInferPayload())
    inferResult.value = normalizeLatest(normalizePayload(result))
  } catch (error) {
    inferError.value = error.message || 'mock 推理失败，请稍后重试'
  } finally {
    inferLoading.value = false
  }
}

function validateFilters() {
  if (!filters.deviceId) {
    return '设备编号不能为空'
  }

  if (!filters.startTime) {
    return '开始时间不能为空'
  }

  if (!filters.endTime) {
    return '结束时间不能为空'
  }

  if (filters.startTime >= filters.endTime) {
    return '开始时间必须早于结束时间'
  }

  return ''
}

function validateInferForm() {
  if (!inferForm.deviceId) {
    return 'mock 推理的设备编号不能为空'
  }

  if (!inferForm.tsEnd) {
    return 'mock 推理的 ts_end 不能为空'
  }

  if (!inferForm.windowMinutes) {
    return 'mock 推理的 window_minutes 不能为空'
  }

  const windowMinutes = Number.parseInt(inferForm.windowMinutes, 10)
  if (!Number.isFinite(windowMinutes) || windowMinutes <= 0) {
    return 'mock 推理的 window_minutes 必须为正整数'
  }

  return ''
}

function buildQueryParams() {
  return {
    device_id: filters.deviceId,
    start_time: filters.startTime,
    end_time: filters.endTime
  }
}

function buildInferPayload() {
  return {
    device_id: inferForm.deviceId,
    ts_end: inferForm.tsEnd,
    window_minutes: Number.parseInt(inferForm.windowMinutes, 10)
  }
}

function normalizePayload(result) {
  return result?.data && typeof result.data === 'object' ? result.data : result
}

function normalizeLatest(record) {
  if (!record || typeof record !== 'object') {
    return null
  }

  return {
    device_id: record.device_id ?? null,
    ts_end: record.ts_end || '',
    window_minutes: toFiniteNumber(record.window_minutes),
    risk_score: getRiskScore(record),
    health_score: toFiniteNumber(record.health_score),
    risk_std: toFiniteNumber(record.risk_std),
    alert_level: record.alert_level || '',
    condition_label: record.condition_label || '',
    model_version: record.model_version || '',
    window_start_time: record.window_start_time || '',
    window_end_time: record.window_end_time || ''
  }
}

function normalizeHistory(records) {
  const sourceRecords = extractHistoryRecords(records)

  return sourceRecords
    .map((item) => normalizeLatest(item))
    .filter((item) => item && (item.window_end_time || item.window_start_time))
    .sort((a, b) => getRecordTime(a).localeCompare(getRecordTime(b)))
}

function extractHistoryRecords(source) {
  if (Array.isArray(source)) {
    return source
  }

  if (!source || typeof source !== 'object') {
    return []
  }

  const candidates = [source.items, source.records, source.series, source.list, source.data]

  for (const item of candidates) {
    if (Array.isArray(item)) {
      return item
    }
  }

  return []
}

function getRiskScore(record) {
  const primaryValue = toFiniteNumber(record?.risk_score)
  if (primaryValue !== null) {
    return primaryValue
  }

  return toFiniteNumber(record?.calibrated_risk_score)
}

function formatNumber(value, digits = 2) {
  const normalizedValue = toFiniteNumber(value)
  return normalizedValue === null ? '-' : normalizedValue.toFixed(digits)
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const normalizedValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(normalizedValue) ? normalizedValue : null
}

function getRecordTime(record) {
  return record?.window_end_time || record?.window_start_time || ''
}

function displayText(value) {
  return value === null || value === undefined || value === '' ? '-' : String(value)
}

function normalizeQueryDeviceId(value) {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0].trim() : ''
  }

  return typeof value === 'string' ? value.trim() : ''
}
</script>

<style scoped>
.prediction-page,
.prediction-panel,
.prediction-infer-card {
  display: grid;
  gap: var(--rail-gap-lg);
}

.prediction-filter-grid {
  grid-template-columns: minmax(140px, 0.65fr) repeat(2, minmax(240px, 1fr));
}

.prediction-panel,
.prediction-infer-card {
  padding: 22px;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(251, 250, 247, 0.9));
  box-shadow: var(--rail-shadow-md);
}

.prediction-panel__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.prediction-overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.prediction-chart-grid,
.prediction-infer-grid {
  display: grid;
  gap: var(--rail-gap-lg);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.prediction-infer-grid {
  grid-template-columns: minmax(140px, 0.65fr) minmax(260px, 1fr) minmax(140px, 0.5fr);
}

.prediction-infer-form {
  display: grid;
  gap: 18px;
}

.prediction-infer-form__actions {
  margin-top: 0;
}

.prediction-infer-result {
  display: grid;
  gap: 18px;
}

@media (max-width: 1180px) {
  .prediction-overview-grid,
  .prediction-chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .prediction-panel,
  .prediction-infer-card {
    padding: 20px;
  }

  .prediction-filter-grid,
  .prediction-overview-grid,
  .prediction-chart-grid,
  .prediction-infer-grid {
    grid-template-columns: 1fr;
  }

  .prediction-panel__meta {
    align-items: flex-start;
  }
}
</style>
