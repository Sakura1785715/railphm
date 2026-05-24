<template>
  <section class="run-record-detail-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">运行记录详情</p>
        <h2>{{ displayText(runRecord?.run_record_code, '运行记录详情') }}</h2>
        <p class="page-description">
          {{ displayText(runRecord?.device_code, '--') }} / {{ displayText(runRecord?.source_segment, '--') }}
        </p>
      </div>

      <div class="detail-actions">
        <RouterLink class="secondary-button" :to="{ name: 'run-records' }">返回列表</RouterLink>
        <button type="button" class="secondary-button" :disabled="randomLoading" @click="handleRandom">
          {{ randomLoading ? '切换中...' : '随机切换' }}
        </button>
        <button type="button" class="primary-button" :disabled="inferLoading || initialLoading" @click="handleInfer">
          {{ inferLoading ? '预测中...' : '执行逐秒预测' }}
        </button>
        <button type="button" class="secondary-button" :disabled="alertLoading || initialLoading" @click="handleAlert">
          {{ alertLoading ? '处理中...' : '生成运行记录告警' }}
        </button>
        <button type="button" class="secondary-button" :disabled="initialLoading" @click="loadPage">
          刷新
        </button>
      </div>
    </div>

    <div v-if="feedbackMessage" :class="['state-panel', feedbackToneClass]">
      {{ feedbackMessage }}
    </div>

    <div v-if="initialLoading" class="state-panel loading-state">正在加载运行记录详情...</div>
    <div v-if="errorMessage" class="state-panel error-state">运行记录详情加载失败：{{ errorMessage }}</div>

    <div class="monitor-overview-grid run-record-summary-grid">
      <article v-for="card in summaryCards" :key="card.key" class="monitor-overview-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </article>
    </div>

    <section class="monitor-section detail-panel">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">监测曲线</p>
          <h3>原始 1 秒采样监测数据</h3>
        </div>
        <p>当前返回 {{ monitorRows.length }} 个监测点，数据按 source_segment 边界查询。</p>
      </div>

      <LineTrendChart
        title="速度与制动参考"
        description="展示 speed、service_brake_speed 与 emergency_brake_speed 的运行变化。"
        :x-axis-data="monitorXAxis"
        :series="monitorSpeedSeries"
        :loading="monitorLoading"
        :empty="monitorRows.length === 0"
        :error="monitorError"
        height="360px"
      />

      <div class="detail-chart-grid">
        <LineTrendChart
          title="环境温度"
          description="展示 outdoor_temperature 随时间变化。"
          :x-axis-data="monitorXAxis"
          :series="temperatureSeries"
          :loading="monitorLoading"
          :empty="monitorRows.length === 0"
          :error="monitorError"
          height="280px"
        />
        <LineTrendChart
          title="环境湿度"
          description="展示 humidity 随时间变化。"
          :x-axis-data="monitorXAxis"
          :series="humiditySeries"
          :loading="monitorLoading"
          :empty="monitorRows.length === 0"
          :error="monitorError"
          height="280px"
        />
      </div>
    </section>

    <section class="monitor-section detail-panel">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">逐秒风险预测</p>
          <h3>风险趋势与健康度趋势</h3>
        </div>
        <p>推理请求固定使用 inference_stride_seconds=1，风险点时间以后端返回为准。</p>
      </div>

      <div v-if="!riskResult" class="state-panel empty-state">
        点击“执行逐秒预测”后展示 risk_series 与 health_series；前 30 秒窗口不足没有风险点属于正常现象。
      </div>

      <div v-else class="detail-chart-grid">
        <MetricTrendChart
          title="风险分数趋势"
          description="展示 risk_score 随推理时间变化。"
          metric-name="风险分数"
          :points="riskTrendPoints"
          :tooltip-details="riskTooltipDetails"
          :loading="inferLoading"
          :error="inferError"
          height="330px"
        />
        <MetricTrendChart
          title="健康度趋势"
          description="展示 health_score 随推理时间变化。"
          metric-name="健康度"
          :points="healthTrendPoints"
          :tooltip-details="healthTooltipDetails"
          :loading="inferLoading"
          :error="inferError"
          height="330px"
        />
      </div>

      <div v-if="riskResult" class="risk-result-summary">
        <article v-for="card in inferSummaryCards" :key="card.key" class="monitor-overview-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
        </article>
      </div>
    </section>

    <section class="detail-grid">
      <article class="monitor-section detail-panel">
        <div class="monitor-section__header">
          <div>
            <p class="section-tag">工况变化</p>
            <h3>工况时间轴</h3>
          </div>
          <p>按相邻相同工况合并展示。</p>
        </div>

        <div v-if="conditionSegments.length" class="condition-list">
          <div v-for="segment in conditionSegments" :key="segment.key" class="condition-item">
            <strong>{{ displayText(segment.label, '--') }}</strong>
            <span>{{ formatDateTime(segment.start, '--') }} ~ {{ formatDateTime(segment.end, '--') }}</span>
            <small>{{ segment.count }} 点</small>
          </div>
        </div>
        <div v-else class="state-panel empty-state">暂无可展示的工况标签。</div>
      </article>

      <article class="monitor-section detail-panel">
        <div class="monitor-section__header">
          <div>
            <p class="section-tag">运行记录告警</p>
            <h3>主告警结果</h3>
          </div>
          <p>告警以整条运行记录最高风险点为代表点。</p>
        </div>

        <div v-if="alertResult" class="alert-result-card">
          <span :class="['record-tag', `record-tag--${getRiskTone(alertResult.alert_level || alertResult.max_alert_level)}`]">
            {{ alertResult.alert_generated === false ? '未生成正式告警' : formatRunRecordRisk(alertResult.alert_level || alertResult.max_alert_level) }}
          </span>
          <strong>{{ alertMessage }}</strong>
          <dl class="alert-result-grid">
            <div>
              <dt>告警ID</dt>
              <dd>{{ displayText(alertResult.alert_id, '--') }}</dd>
            </div>
            <div>
              <dt>风险结果ID</dt>
              <dd>{{ displayText(alertResult.risk_result_id || alertResult.max_risk_result_id, '--') }}</dd>
            </div>
            <div>
              <dt>最高风险</dt>
              <dd>{{ formatPercent(alertResult.max_risk_score, 2, '--') }}</dd>
            </div>
            <div>
              <dt>健康度</dt>
              <dd>{{ formatScore(alertResult.health_score, 2, '--') }}</dd>
            </div>
            <div>
              <dt>创建状态</dt>
              <dd>{{ formatAlertCreateState(alertResult) }}</dd>
            </div>
          </dl>
        </div>
        <div v-else class="state-panel empty-state">
          点击“生成运行记录告警”后展示主告警结果。
        </div>
      </article>
    </section>

    <section class="monitor-section detail-panel">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">风险点明细</p>
          <h3>高风险点与推理结果</h3>
        </div>
        <p>展示前 120 个风险点，完整结果用于曲线绘制。</p>
      </div>

      <div v-if="riskRows.length" class="detail-table-wrapper">
        <table class="detail-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>风险分数</th>
              <th>风险波动</th>
              <th>健康度</th>
              <th>健康状态</th>
              <th>工况</th>
              <th>持久化状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in riskRows" :key="row.key">
              <td>{{ formatDateTime(row.time || row.window_end_time, '--') }}</td>
              <td>{{ formatPercent(row.risk_score, 2, '--') }}</td>
              <td>{{ formatPercent(row.risk_std, 2, '--') }}</td>
              <td>{{ formatScore(row.health_score, 2, '--') }}</td>
              <td>{{ displayText(row.health_status || row.health_level, '--') }}</td>
              <td>{{ displayText(row.condition_label, '--') }}</td>
              <td>{{ formatPersistStatus(row.persist_status) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="state-panel empty-state">
        暂无风险点明细。
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LineTrendChart, MetricTrendChart } from '../components/chart'
import {
  generateRunRecordAlert,
  getRandomRunRecord,
  getRunRecordDetail,
  getRunRecordMonitor,
  inferRunRecord
} from '../api/runRecord'
import {
  displayText,
  formatDateTime,
  formatPercent,
  formatScore,
  toFiniteNumber
} from '../utils/formatters'

const DEFAULT_INFERENCE_STRIDE_SECONDS = 1

const route = useRoute()
const router = useRouter()

const runRecord = ref(null)
const monitorData = ref(null)
const riskResult = ref(null)
const alertResult = ref(null)
const initialLoading = ref(false)
const monitorLoading = ref(false)
const inferLoading = ref(false)
const alertLoading = ref(false)
const randomLoading = ref(false)
const errorMessage = ref('')
const monitorError = ref('')
const inferError = ref('')
const feedbackMessage = ref('')
const feedbackTone = ref('success')

const runRecordId = computed(() => route.params.id)
const monitorRows = computed(() => {
  const rows = monitorData.value?.series
  return Array.isArray(rows) ? rows : []
})
const monitorXAxis = computed(() => monitorRows.value.map((row) => row.sample_time || row.time).filter(Boolean))
const monitorSpeedSeries = computed(() => [
  {
    name: '速度',
    unit: 'km/h',
    data: monitorRows.value.map((row) => toNumberOrNull(row.speed))
  },
  {
    name: '常用制动速度',
    unit: 'km/h',
    data: monitorRows.value.map((row) => toNumberOrNull(row.service_brake_speed))
  },
  {
    name: '紧急制动速度',
    unit: 'km/h',
    data: monitorRows.value.map((row) => toNumberOrNull(row.emergency_brake_speed))
  }
])
const temperatureSeries = computed(() => [
  {
    name: '室外温度',
    unit: '℃',
    data: monitorRows.value.map((row) => toNumberOrNull(row.outdoor_temperature)),
    area: true
  }
])
const humiditySeries = computed(() => [
  {
    name: '湿度',
    unit: '%',
    data: monitorRows.value.map((row) => toNumberOrNull(row.humidity)),
    area: true
  }
])
const riskSeries = computed(() => {
  const rows = riskResult.value?.risk_series
  return Array.isArray(rows) ? rows : []
})
const healthSeries = computed(() => {
  const rows = riskResult.value?.health_series
  if (Array.isArray(rows) && rows.length > 0) {
    return rows
  }

  return riskSeries.value
    .map((point) => {
      const riskScore = toNumberOrNull(point.risk_score)
      if (riskScore === null) {
        return null
      }

      return {
        time: point.time || point.window_end_time,
        window_end_time: point.window_end_time,
        health_score: 100 * (1 - riskScore),
        health_level: point.health_level,
        health_status: point.health_status,
        source_segment: point.source_segment
      }
    })
    .filter(Boolean)
})
const riskTrendPoints = computed(() =>
  riskSeries.value
    .map((point) => ({
      time: point.time || point.window_end_time,
      value: toNumberOrNull(point.risk_score)
    }))
    .filter((point) => point.time && point.value !== null)
)
const healthTrendPoints = computed(() =>
  healthSeries.value
    .map((point) => ({
      time: point.time || point.window_end_time,
      value: toNumberOrNull(point.health_score)
    }))
    .filter((point) => point.time && point.value !== null)
)
const riskTooltipDetails = computed(() =>
  riskSeries.value.map((point) => [
    { label: '窗口结束', value: formatDateTime(point.window_end_time || point.time, '--') },
    { label: '风险波动', value: formatPercent(point.risk_std, 2, '--') },
    { label: '工况', value: displayText(point.condition_label, '--') },
    { label: '持久化', value: formatPersistStatus(point.persist_status) }
  ])
)
const healthTooltipDetails = computed(() =>
  healthSeries.value.map((point) => [
    { label: '健康等级', value: displayText(point.health_level || point.health_status, '--') },
    { label: 'source_segment', value: displayText(point.source_segment, '--') }
  ])
)
const riskRows = computed(() =>
  riskSeries.value.slice(0, 120).map((row, index) => ({
    ...row,
    key: `${row.time || row.window_end_time || index}-${index}`
  }))
)
const conditionSourceRows = computed(() => (riskSeries.value.length > 0 ? riskSeries.value : monitorRows.value))
const conditionSegments = computed(() => {
  const segments = []
  let active = null
  conditionSourceRows.value.forEach((row, index) => {
    const label = row.condition_label || '未标注'
    const time = row.time || row.window_end_time || row.sample_time
    if (!active || active.label !== label) {
      if (active) {
        segments.push(active)
      }
      active = {
        key: `${label}-${index}`,
        label,
        start: time,
        end: time,
        count: 1
      }
    } else {
      active.end = time
      active.count += 1
    }
  })
  if (active) segments.push(active)
  return segments.slice(0, 18)
})
const summaryCards = computed(() => [
  { key: 'device', label: '设备编号', value: displayText(runRecord.value?.device_code, '--') },
  { key: 'segment', label: 'source_segment', value: displayText(runRecord.value?.source_segment, '--') },
  {
    key: 'time',
    label: '运行时间',
    value: `${formatDateTime(runRecord.value?.record_start_time, '--')} ~ ${formatDateTime(runRecord.value?.record_end_time, '--')}`
  },
  { key: 'points', label: '监测点数', value: formatInteger(runRecord.value?.point_count) },
  { key: 'duration', label: '持续时长', value: formatDuration(runRecord.value?.duration_seconds) },
  { key: 'status', label: '状态', value: formatRunRecordStatus(runRecord.value?.status) },
  { key: 'risk', label: '最高风险', value: formatPercent(runRecord.value?.max_risk_score, 2, '--') },
  { key: 'level', label: '告警等级', value: formatRunRecordRisk(runRecord.value?.max_alert_level) }
])
const inferSummaryCards = computed(() => [
  { key: 'monitor', label: '监测点数', value: formatInteger(riskResult.value?.monitor_point_count) },
  { key: 'result', label: '风险点数', value: formatInteger(riskResult.value?.result_count) },
  { key: 'saved', label: '新保存', value: formatInteger(riskResult.value?.saved_count) },
  { key: 'existing', label: '复用已有', value: formatInteger(riskResult.value?.skipped_existing_count) },
  { key: 'max', label: '最高风险', value: formatPercent(riskResult.value?.max_risk_score, 2, '--') },
  { key: 'level', label: '最高等级', value: formatRunRecordRisk(riskResult.value?.max_alert_level) }
])
const feedbackToneClass = computed(() => (feedbackTone.value === 'error' ? 'error-state' : 'success-state'))
const alertMessage = computed(() => {
  if (!alertResult.value) return ''
  if (alertResult.value.alert_generated === false) {
    return '最高风险未达到预警阈值，未生成正式告警'
  }
  if (alertResult.value.existing) {
    return '该运行记录已存在告警'
  }
  return alertResult.value.message || alertResult.value.alert?.alert_message || '告警处理完成'
})

onMounted(() => {
  loadPage()
})

watch(
  () => route.params.id,
  () => {
    riskResult.value = null
    alertResult.value = null
    loadPage()
  }
)

async function loadPage() {
  initialLoading.value = true
  errorMessage.value = ''
  clearFeedback()
  try {
    const [detailResult, monitorResult] = await Promise.all([
      getRunRecordDetail(runRecordId.value),
      loadMonitor()
    ])
    runRecord.value = normalizePayload(detailResult)
    monitorData.value = normalizePayload(monitorResult)
  } catch (error) {
    errorMessage.value = error.message || '无法加载运行记录详情'
  } finally {
    initialLoading.value = false
  }
}

async function loadMonitor() {
  monitorLoading.value = true
  monitorError.value = ''
  try {
    return await getRunRecordMonitor(runRecordId.value)
  } catch (error) {
    monitorError.value = error.message || '无法加载监测数据'
    throw error
  } finally {
    monitorLoading.value = false
  }
}

async function handleInfer() {
  inferLoading.value = true
  inferError.value = ''
  clearFeedback()
  try {
    const result = await inferRunRecord(runRecordId.value, {
      mc_samples: 20,
      persist: true,
      generate_alert: false,
      inference_stride_seconds: DEFAULT_INFERENCE_STRIDE_SECONDS
    })
    riskResult.value = normalizePayload(result)
    runRecord.value = {
      ...(runRecord.value || {}),
      status: riskResult.value.run_record_status || 'inferred',
      max_risk_score: riskResult.value.max_risk_score,
      max_risk_result_id: riskResult.value.max_risk_result_id,
      max_alert_level: riskResult.value.max_alert_level
    }
    const skippedExisting = Number(riskResult.value.skipped_existing_count) || 0
    showFeedback(skippedExisting > 0 && Number(riskResult.value.saved_count) === 0 ? '已加载已有预测结果' : '预测完成')
  } catch (error) {
    inferError.value = error.message || '执行逐秒预测失败'
    showFeedback(inferError.value, 'error')
  } finally {
    inferLoading.value = false
  }
}

async function handleAlert() {
  alertLoading.value = true
  clearFeedback()
  try {
    const result = await generateRunRecordAlert(runRecordId.value, {})
    alertResult.value = normalizePayload(result)
    runRecord.value = {
      ...(runRecord.value || {}),
      status: alertResult.value.alert_generated === false ? 'inferred' : 'alerted',
      alert_id: alertResult.value.alert_id || runRecord.value?.alert_id,
      max_risk_score: alertResult.value.max_risk_score ?? runRecord.value?.max_risk_score,
      max_risk_result_id:
        alertResult.value.max_risk_result_id ??
        alertResult.value.risk_result_id ??
        runRecord.value?.max_risk_result_id,
      max_alert_level: alertResult.value.max_alert_level ?? alertResult.value.alert_level ?? runRecord.value?.max_alert_level
    }
    if (alertResult.value.existing) {
      showFeedback('该运行记录已存在告警')
    } else if (alertResult.value.alert_generated === false) {
      showFeedback('最高风险未达到预警阈值，未生成正式告警')
    } else {
      showFeedback('告警处理完成')
    }
  } catch (error) {
    showFeedback(error.message || '生成运行记录告警失败', 'error')
  } finally {
    alertLoading.value = false
  }
}

async function handleRandom() {
  randomLoading.value = true
  clearFeedback()
  try {
    const result = await getRandomRunRecord()
    const record = normalizePayload(result)
    if (record?.run_record_id) {
      router.push({ name: 'run-record-detail', params: { id: record.run_record_id } })
    } else {
      showFeedback('未找到可用运行记录', 'error')
    }
  } catch (error) {
    showFeedback(error.message || '随机切换失败', 'error')
  } finally {
    randomLoading.value = false
  }
}

function normalizePayload(result) {
  return result?.data && typeof result.data === 'object' ? result.data : result
}

function showFeedback(message, tone = 'success') {
  feedbackMessage.value = message
  feedbackTone.value = tone
}

function clearFeedback() {
  feedbackMessage.value = ''
  feedbackTone.value = 'success'
}

function toNumberOrNull(value) {
  return toFiniteNumber(value)
}

function formatInteger(value) {
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? '--' : Math.round(numericValue).toLocaleString('zh-CN')
}

function formatDuration(value) {
  const seconds = toFiniteNumber(value)
  if (seconds === null) return '--'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return rest > 0 ? `${minutes} 分 ${rest} 秒` : `${minutes} 分`
}

function formatRunRecordStatus(status) {
  const statusMap = {
    ready: '未分析',
    inferred: '已预测',
    alerted: '已告警',
    ignored: '已忽略'
  }
  return statusMap[status] || displayText(status, '--')
}

function formatRunRecordRisk(level) {
  const riskMap = {
    high: '严重',
    medium: '预警',
    low: '关注',
    attention: '关注',
    normal: '正常',
    none: '正常'
  }
  return riskMap[String(level || '').toLowerCase()] || '--'
}

function getRiskTone(level) {
  const normalized = String(level || '').toLowerCase()
  if (normalized === 'high') return 'danger'
  if (normalized === 'medium') return 'warning'
  if (normalized === 'low' || normalized === 'attention') return 'notice'
  return 'success'
}

function formatPersistStatus(status) {
  const map = {
    saved: '已保存',
    skipped_existing: '已存在',
    not_persisted: '未保存'
  }
  return map[status] || displayText(status, '--')
}

function formatAlertCreateState(result) {
  if (result.existing) return '已存在'
  if (result.created) return '新生成'
  if (result.alert_generated === false) return '未生成'
  return '--'
}
</script>

<style scoped>
.run-record-detail-page {
  width: 100%;
  max-width: var(--layout-page-max);
  margin: 0 auto;
  display: grid;
  gap: var(--space-6);
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-3);
}

.run-record-summary-grid,
.risk-result-summary {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.detail-panel {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
}

.detail-chart-grid,
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.risk-result-summary {
  display: grid;
  gap: var(--space-4);
}

.condition-list {
  display: grid;
  gap: var(--space-3);
}

.condition-item {
  display: grid;
  grid-template-columns: minmax(120px, 0.8fr) minmax(0, 1.6fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.condition-item strong {
  color: var(--color-text-primary);
}

.condition-item span,
.condition-item small {
  color: var(--color-text-secondary);
}

.alert-result-card {
  display: grid;
  gap: var(--space-4);
}

.alert-result-card > strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.alert-result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
  margin: 0;
}

.alert-result-grid div {
  display: grid;
  gap: 4px;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.alert-result-grid dt {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 720;
}

.alert-result-grid dd {
  margin: 0;
  color: var(--color-text-primary);
  font-weight: 760;
}

.detail-table-wrapper {
  min-width: 0;
  overflow-x: auto;
}

.detail-table {
  width: 100%;
  min-width: 920px;
  border-collapse: collapse;
}

.detail-table th,
.detail-table td {
  padding: 12px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
}

.detail-table th {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  background: var(--color-bg-panel);
}

.record-tag {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: #fff;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 760;
}

.record-tag--danger {
  border-color: rgba(220, 38, 38, 0.24);
  background: rgba(220, 38, 38, 0.08);
  color: #b91c1c;
}

.record-tag--warning {
  border-color: rgba(217, 119, 6, 0.26);
  background: rgba(217, 119, 6, 0.1);
  color: #b45309;
}

.record-tag--notice {
  border-color: rgba(29, 79, 145, 0.22);
  background: rgba(29, 79, 145, 0.08);
  color: var(--color-primary);
}

.record-tag--success {
  border-color: rgba(22, 163, 74, 0.24);
  background: rgba(22, 163, 74, 0.09);
  color: #15803d;
}

@media (max-width: 1080px) {
  .detail-chart-grid,
  .detail-grid,
  .run-record-summary-grid,
  .risk-result-summary {
    grid-template-columns: 1fr;
  }

  .condition-item {
    grid-template-columns: 1fr;
  }
}
</style>
