<template>
  <section class="alert-diagnosis-page">
    <PageHeader
      title="告警研判详情"
      eyebrow="系统首页 / 告警中心 / 告警研判详情"
      description="围绕单条告警汇聚风险趋势、健康趋势、运行监测曲线、工况分段与处置记录。"
      :meta="pageMetaText"
    >
      <template #actions>
        <RouterLink class="secondary-button" :to="{ name: 'alerts' }">返回告警中心</RouterLink>
        <button class="secondary-button" type="button" :disabled="loading" @click="loadDiagnosis">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </template>
    </PageHeader>

    <div v-if="feedbackMessage" :class="['state-panel', feedbackTone === 'error' ? 'error-state' : 'success-state']">
      {{ feedbackMessage }}
    </div>

    <LoadingBlock v-if="loading && !diagnosis" text="正在加载告警研判数据..." height="320px" />

    <ErrorState
      v-else-if="errorMessage"
      title="告警研判数据加载失败"
      :message="errorMessage"
      retry-text="重新加载"
      @retry="loadDiagnosis"
    />

    <EmptyState
      v-else-if="!diagnosis"
      title="暂无告警研判数据"
      description="当前告警未返回可展示的研判信息。"
    />

    <template v-else>
      <section class="diagnosis-overview">
        <header class="diagnosis-section-title">
          <p class="section-tag">告警概览</p>
          <h3>告警概览</h3>
        </header>

        <div class="overview-info-grid">
          <dl class="overview-info-list">
            <div v-for="item in alertBaseInfo" :key="item.key">
              <dt>{{ item.label }}</dt>
              <dd>
                <span v-if="item.badge" :class="['alert-badge', `alert-badge--${item.tone}`]">
                  {{ item.value }}
                </span>
                <template v-else>{{ item.value }}</template>
              </dd>
            </div>
          </dl>

          <dl class="overview-info-list">
            <div v-for="item in runBaseInfo" :key="item.key">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>

          <div class="overview-metric-grid">
            <article
              v-for="metric in overviewMetrics"
              :key="metric.key"
              :class="['overview-metric', `overview-metric--${metric.tone}`]"
            >
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
              <small>{{ metric.description }}</small>
            </article>
          </div>
        </div>
      </section>

      <section class="diagnosis-summary-panel">
        <div class="diagnosis-summary-copy">
          <p class="section-tag">诊断摘要</p>
          <h3>诊断摘要</h3>
          <p>{{ diagnosisEvidenceText }}</p>
        </div>

        <div class="diagnosis-summary-metrics">
          <article v-for="item in summaryMetrics" :key="item.key">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="trend-grid">
        <article class="diagnosis-panel">
          <div class="panel-heading">
            <div>
              <p class="section-tag">风险趋势</p>
              <h3>风险趋势</h3>
            </div>
            <span class="event-chip">告警触发 {{ formatDateTime(summary.event_time, '--') }}</span>
          </div>
          <MetricTrendChart
            metric-name="风险分数"
            :points="riskTrendPoints"
            :tooltip-details="riskTooltipDetails"
            :loading="loading"
            :error="riskTrendError"
            height="320px"
          />
          <p v-if="riskTrendPoints.length" class="trend-event-note trend-event-note--risk">
            代表告警点：{{ formatDateTime(summary.event_time, '--') }} / {{ eventRiskText }}
          </p>
          <EmptyState
            v-if="!loading && riskTrendPoints.length === 0"
            title="暂无风险趋势数据"
            description="diagnosis 接口未返回 risk_series。"
          />
        </article>

        <article class="diagnosis-panel">
          <div class="panel-heading">
            <div>
              <p class="section-tag">健康度趋势</p>
              <h3>健康度趋势</h3>
            </div>
            <span class="event-chip">告警触发 {{ formatDateTime(summary.event_time, '--') }}</span>
          </div>
          <MetricTrendChart
            metric-name="健康度"
            unit="%"
            :points="healthTrendPoints"
            :tooltip-details="healthTooltipDetails"
            :loading="loading"
            :error="healthTrendError"
            height="320px"
          />
          <p v-if="healthTrendPoints.length" class="trend-event-note trend-event-note--health">
            代表告警点：{{ formatDateTime(summary.event_time, '--') }} / {{ eventHealthText }}
          </p>
          <EmptyState
            v-if="!loading && healthTrendPoints.length === 0"
            title="暂无健康度趋势数据"
            description="diagnosis 接口未返回 health_series 或可兜底的健康度字段。"
          />
        </article>
      </section>

      <section class="diagnosis-panel monitor-analysis-panel">
        <div class="panel-heading">
          <div>
            <p class="section-tag">运行监测分析</p>
            <h3>运行监测分析</h3>
          </div>
          <span class="event-chip">监测点 {{ formatInteger(monitorRows.length) }}</span>
        </div>

        <div class="monitor-tabs" role="tablist" aria-label="运行监测分析维度">
          <button
            v-for="tab in monitorTabs"
            :key="tab.key"
            :class="['monitor-tab', { 'monitor-tab--active': activeMonitorTab === tab.key }]"
            type="button"
            @click="activeMonitorTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <LineTrendChart
          v-if="activeMonitorTab === 'speed'"
          :x-axis-data="monitorXAxis"
          :series="speedBrakeSeries"
          :loading="loading"
          :empty="monitorRows.length === 0"
          height="360px"
        />
        <LineTrendChart
          v-else-if="activeMonitorTab === 'environment'"
          :x-axis-data="monitorXAxis"
          :series="environmentSeries"
          :loading="loading"
          :empty="monitorRows.length === 0"
          height="360px"
        />
        <div v-else class="position-analysis-grid">
          <LineTrendChart
            :x-axis-data="monitorXAxis"
            :series="positionSeries"
            :loading="loading"
            :empty="monitorRows.length === 0"
            height="320px"
          />
          <dl class="position-summary">
            <div v-for="item in positionSummary" :key="item.key">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section class="diagnosis-panel">
        <div class="panel-heading">
          <div>
            <p class="section-tag">工况分段</p>
            <h3>工况分段</h3>
          </div>
          <span class="event-chip">共 {{ conditionTimeline.length }} 段</span>
        </div>

        <div v-if="conditionTimeline.length" class="condition-timeline">
          <div class="condition-timeline__bar">
            <article
              v-for="segment in conditionTimeline"
              :key="segment.key"
              :class="['condition-segment', `condition-segment--${segment.tone}`, { 'condition-segment--active': segment.active }]"
              :style="{ flexBasis: `${segment.width}%` }"
              :title="`${segment.label} ${segment.startText} ~ ${segment.endText}`"
            >
              <strong>{{ segment.label }}</strong>
            </article>
          </div>
          <div class="condition-timeline__legend">
            <article v-for="segment in conditionTimeline" :key="`${segment.key}-legend`">
              <span :class="['condition-dot', `condition-dot--${segment.tone}`]" aria-hidden="true"></span>
              <strong>{{ segment.label }}</strong>
              <small>{{ segment.startText }} ~ {{ segment.endText }} / {{ segment.pointCount }} 点</small>
            </article>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无工况分段"
          description="diagnosis 接口未返回 condition_segments。"
        />
      </section>

      <section class="handle-grid">
        <article class="diagnosis-panel">
          <div class="panel-heading">
            <div>
              <p class="section-tag">处理记录</p>
              <h3>处理记录与告警处置</h3>
            </div>
          </div>
          <dl class="handle-record-list">
            <div v-for="item in handleRecordFields" :key="item.key">
              <dt>{{ item.label }}</dt>
              <dd>
                <span v-if="item.badge" :class="['alert-badge', `alert-badge--${item.tone}`]">
                  {{ item.value }}
                </span>
                <template v-else>{{ item.value }}</template>
              </dd>
            </div>
          </dl>
        </article>

        <article class="diagnosis-panel">
          <div class="panel-heading">
            <div>
              <p class="section-tag">告警处置操作</p>
              <h3>告警处置操作</h3>
            </div>
            <span v-if="!canHandleAlert" class="event-chip">无处置权限</span>
          </div>

          <form v-if="canHandleAlert" class="handle-form" @submit.prevent="submitHandle('save')">
            <label class="handle-field">
              <span>处置说明 <strong>*</strong></span>
              <textarea
                v-model="handleForm.handleNote"
                maxlength="200"
                placeholder="请输入处置说明，建议描述排查结论或备注信息（至少5个字）"
                :disabled="handleSubmitting"
              ></textarea>
              <small>{{ handleForm.handleNote.length }}/200</small>
            </label>

            <label class="handle-field">
              <span>处理人ID <strong>*</strong></span>
              <input
                v-model.trim="handleForm.handlerId"
                type="text"
                inputmode="numeric"
                placeholder="请输入处理人ID"
                :disabled="handleSubmitting"
              />
            </label>

            <div v-if="handleError" class="state-panel error-state handle-message">
              {{ handleError }}
            </div>

            <div class="handle-actions">
              <button
                class="secondary-button"
                type="button"
                :disabled="handleSubmitting || isCurrentResolved"
                @click="submitHandle('processing')"
              >
                标记处理中
              </button>
              <button
                class="secondary-button handle-actions__resolved"
                type="button"
                :disabled="handleSubmitting"
                @click="submitHandle('resolved')"
              >
                标记已处理
              </button>
              <button class="primary-button" type="submit" :disabled="handleSubmitting">
                {{ handleSubmitting ? '保存中...' : '保存处置' }}
              </button>
            </div>
          </form>

          <EmptyState
            v-else
            title="当前账号暂无告警处置权限"
            description="仅 OPS 或 ADMIN 角色可提交告警处置。"
          />
        </article>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getAlertDiagnosis, updateAlertStatus } from '../api/alert'
import { LineTrendChart, MetricTrendChart } from '../components/chart'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingBlock from '../components/common/LoadingBlock.vue'
import PageHeader from '../components/common/PageHeader.vue'
import { getStoredUser, hasAnyRole } from '../utils/auth'
import {
  displayText,
  formatAlertLevel,
  formatAlertStatus,
  formatDateTime,
  formatHealthScore,
  formatPercent,
  toFiniteNumber
} from '../utils/formatters'
import { DEFAULT_EMA_ALPHA, applyEmaToPoints } from '../utils/seriesSmoothing'

const route = useRoute()
const RISK_TREND_EMA_ALPHA = DEFAULT_EMA_ALPHA

const diagnosis = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const feedbackMessage = ref('')
const feedbackTone = ref('success')
const activeMonitorTab = ref('speed')
const handleSubmitting = ref(false)
const handleError = ref('')
const handleForm = reactive({
  handlerId: '',
  handleNote: ''
})
let requestId = 0
let feedbackTimer = 0

const monitorTabs = [
  { key: 'speed', label: '速度与制动' },
  { key: 'environment', label: '环境与工况' },
  { key: 'position', label: '位置与运行' }
]

const alertId = computed(() => route.params.id)
const alert = computed(() => diagnosis.value?.alert || {})
const runRecord = computed(() => diagnosis.value?.run_record || {})
const representativeRisk = computed(() => diagnosis.value?.representative_risk || {})
const summary = computed(() => diagnosis.value?.diagnosis_summary || {})
const monitorRows = computed(() => normalizeRows(diagnosis.value?.monitor_series))
const riskRows = computed(() => normalizeRows(diagnosis.value?.risk_series))
const healthRows = computed(() => normalizeRows(diagnosis.value?.health_series))
const conditionRows = computed(() => normalizeRows(diagnosis.value?.condition_segments))
const sampledMonitorRows = computed(() => sampleRows(monitorRows.value, 520))
const monitorXAxis = computed(() =>
  sampledMonitorRows.value.map((row) => formatAxisTime(row.sample_time || row.time)).filter(Boolean)
)
const pageMetaText = computed(() => {
  if (loading.value) {
    return '正在刷新告警研判数据。'
  }

  return `告警ID：${displayValue(alertId.value)}`
})
const isCurrentResolved = computed(() => normalizeAlertStatusKey(alert.value.alert_status) === 'resolved')
const canHandleAlert = computed(() => hasAnyRole(['OPS', 'ADMIN']))
const diagnosisEvidenceText = computed(() =>
  displayText(summary.value.evidence_text, '暂无诊断摘要文本，请结合风险趋势、监测曲线和工况分段进行人工研判。')
)
const riskTrendError = computed(() => (riskRows.value.length ? '' : ''))
const healthTrendError = computed(() => (healthRows.value.length || riskRows.value.length ? '' : ''))
const eventRiskText = computed(() =>
  formatRiskScore(representativeRisk.value.risk_score ?? alert.value.risk_score ?? summary.value.max_risk_score)
)
const eventHealthText = computed(() =>
  formatHealthScore(representativeRisk.value.health_score ?? alert.value.health_score ?? summary.value.min_health_score, 2, '--')
)

const alertBaseInfo = computed(() => [
  {
    key: 'level',
    label: '告警等级',
    value: formatAlertLevel(alert.value.alert_level),
    badge: true,
    tone: getRiskTone(alert.value.alert_level)
  },
  {
    key: 'status',
    label: '处理状态',
    value: alert.value.alert_status_text || formatAlertStatus(alert.value.alert_status),
    badge: true,
    tone: getStatusTone(alert.value.alert_status)
  },
  { key: 'device', label: '设备编号', value: displayValue(alert.value.device_code || alert.value.device_id) },
  {
    key: 'alert_time',
    label: '告警生成时间',
    value: formatDateTime(alert.value.alert_time || alert.value.create_time || alert.value.created_at, '--')
  },
  { key: 'event_time', label: '风险触发时间', value: formatDateTime(summary.value.event_time, '--') }
])

const runBaseInfo = computed(() => [
  { key: 'segment', label: '运行片段', value: displayValue(summary.value.source_segment || runRecord.value.source_segment) },
  {
    key: 'run_record',
    label: '运行记录ID',
    value: displayValue(summary.value.run_record_id || alert.value.run_record_id || runRecord.value.run_record_id)
  },
  { key: 'device_type', label: '设备类型', value: displayValue(runRecord.value.atp_type || runRecord.value.device_type) },
  { key: 'train', label: '车次/车组', value: trainCarText.value },
  { key: 'line', label: '运行区段', value: displayValue(runRecord.value.line_id) }
])

const trainCarText = computed(() => {
  const firstRow = monitorRows.value[0] || {}
  const trainNo = firstRow.source_train_no || firstRow.train_no
  const carNo = firstRow.source_car_no || firstRow.car_no

  if (!trainNo && !carNo) {
    return '--'
  }

  return [trainNo, carNo].filter(Boolean).join(' / ')
})

const overviewMetrics = computed(() => [
  {
    key: 'risk',
    label: '风险分数',
    value: formatRiskScore(alert.value.risk_score ?? summary.value.max_risk_score),
    description: getRiskDescription(alert.value.alert_level),
    tone: 'danger'
  },
  {
    key: 'health',
    label: '健康度',
    value: formatHealthScore(alert.value.health_score ?? summary.value.min_health_score, 2, '--'),
    description: '越低风险越高',
    tone: 'success'
  },
  {
    key: 'condition',
    label: '工况标签',
    value: displayValue(focusConditionLabel.value),
    description: '主要工况',
    tone: 'primary'
  }
])

const focusConditionLabel = computed(() => {
  if (representativeRisk.value?.condition_label) {
    return representativeRisk.value.condition_label
  }

  const riskPoint = riskRows.value.find((row) => row.condition_label)
  if (riskPoint) {
    return riskPoint.condition_label
  }

  if (!conditionRows.value.length) {
    return ''
  }

  return [...conditionRows.value].sort((left, right) =>
    toNumber(right.point_count || right.count) - toNumber(left.point_count || left.count)
  )[0]?.label
})

const summaryMetrics = computed(() => [
  {
    key: 'window',
    label: '时间窗口',
    value: `${formatDateTime(summary.value.context_start_time, '--')} ~ ${formatDateTime(summary.value.context_end_time, '--')}`
  },
  { key: 'maxRisk', label: '最大风险分数', value: formatRiskScore(summary.value.max_risk_score) },
  { key: 'minHealth', label: '最低健康度', value: formatHealthScore(summary.value.min_health_score, 2, '--') },
  { key: 'monitorCount', label: '监测点数量', value: formatInteger(summary.value.monitor_point_count) },
  { key: 'riskCount', label: '风险点数量', value: formatInteger(summary.value.risk_point_count) }
])

const riskTrendSourceRows = computed(() =>
  riskRows.value.filter((point) => {
    const time = formatAxisTime(point.time || point.window_end_time)
    return time && toFiniteNumber(point.risk_score) !== null
  })
)

const rawRiskTrendPoints = computed(() =>
  riskTrendSourceRows.value.map((point) => ({
    time: formatAxisTime(point.time || point.window_end_time),
    value: toFiniteNumber(point.risk_score)
  }))
)

// EMA smoothing is only used for visualization.
// Raw risk_score and health_score are still used for alert rules, tables and persisted records.
const riskTrendPoints = computed(() => applyEmaToPoints(rawRiskTrendPoints.value, { alpha: RISK_TREND_EMA_ALPHA }))

const healthTrendSourceRows = computed(() => {
  const sourceRows = healthRows.value.length ? healthRows.value : riskRows.value

  return sourceRows.filter((point) => {
    const time = formatAxisTime(point.time || point.window_end_time)
    return time && toFiniteNumber(point.health_score) !== null
  })
})

const rawHealthTrendPoints = computed(() =>
  healthTrendSourceRows.value.map((point) => ({
    time: formatAxisTime(point.time || point.window_end_time),
    value: toFiniteNumber(point.health_score)
  }))
)

const healthTrendPoints = computed(() => applyEmaToPoints(rawHealthTrendPoints.value, { alpha: RISK_TREND_EMA_ALPHA }))

const riskTooltipDetails = computed(() =>
  riskTrendSourceRows.value.map((point) => [
    { label: '风险原始值', value: formatRiskScore(point.risk_score) },
    { label: '完整时间', value: formatDateTime(point.time || point.window_end_time, '--') },
    { label: '风险波动', value: formatPercent(point.risk_std, 2, '--') },
    { label: '工况', value: displayValue(point.condition_label) },
    { label: '代表点', value: isEventPoint(point) ? '是' : '否' }
  ])
)

const healthTooltipDetails = computed(() => {
  return healthTrendSourceRows.value.map((point) => [
    { label: '健康度原始值', value: formatHealthScore(point.health_score, 2, '--') },
    { label: '完整时间', value: formatDateTime(point.time || point.window_end_time, '--') },
    { label: '健康状态', value: displayValue(point.health_level || point.health_status) },
    { label: '代表点', value: isEventPoint(point) ? '是' : '否' }
  ])
})

const speedBrakeSeries = computed(() => [
  {
    name: 'speed',
    unit: 'km/h',
    data: sampledMonitorRows.value.map((row) => toFiniteNumber(row.speed))
  },
  {
    name: 'service_brake_speed',
    unit: 'km/h',
    data: sampledMonitorRows.value.map((row) => toFiniteNumber(row.service_brake_speed))
  },
  {
    name: 'emergency_brake_speed',
    unit: 'km/h',
    data: sampledMonitorRows.value.map((row) => toFiniteNumber(row.emergency_brake_speed))
  }
])

const environmentSeries = computed(() => [
  {
    name: 'outdoor_temperature',
    unit: '℃',
    data: sampledMonitorRows.value.map((row) => toFiniteNumber(row.outdoor_temperature)),
    area: true
  },
  {
    name: 'humidity',
    unit: '%',
    data: sampledMonitorRows.value.map((row) => toFiniteNumber(row.humidity))
  }
])

const positionSeries = computed(() => [
  {
    name: 'mileage',
    data: sampledMonitorRows.value.map((row) => toFiniteNumber(row.mileage)),
    area: true
  },
  {
    name: 'run_distance',
    data: sampledMonitorRows.value.map((row) => toFiniteNumber(row.run_distance))
  }
])

const positionSummary = computed(() => {
  const firstRow = monitorRows.value[0] || {}
  const lastRow = monitorRows.value[monitorRows.value.length - 1] || {}

  return [
    { key: 'station', label: '站点', value: displayValue(lastRow.station_name || firstRow.station_name) },
    { key: 'longitude', label: '经度', value: displayValue(lastRow.longitude || firstRow.longitude) },
    { key: 'latitude', label: '纬度', value: displayValue(lastRow.latitude || firstRow.latitude) },
    { key: 'mileage', label: '最新里程', value: displayValue(lastRow.mileage) },
    { key: 'distance', label: '运行距离', value: displayValue(lastRow.run_distance) }
  ]
})

const conditionTimeline = computed(() => {
  if (!conditionRows.value.length) {
    return []
  }

  const enrichedRows = conditionRows.value.map((row, index) => ({
    key: `${row.label || row.condition_label || 'segment'}-${index}`,
    label: displayValue(row.label || row.condition_label || row.condition),
    start: row.start_time || row.start || row.context_start_time,
    end: row.end_time || row.end || row.context_end_time,
    pointCount: toNumber(row.point_count || row.count || 0),
    tone: getSegmentTone(index),
    active: isFocusCondition(row.label || row.condition_label || row.condition)
  }))

  const totalDuration = enrichedRows.reduce((sum, row) => sum + getDurationMs(row.start, row.end), 0)
  const totalPoints = enrichedRows.reduce((sum, row) => sum + row.pointCount, 0)

  return enrichedRows.map((row) => {
    const duration = getDurationMs(row.start, row.end)
    const width = totalDuration > 0
      ? (duration / totalDuration) * 100
      : totalPoints > 0
        ? (row.pointCount / totalPoints) * 100
        : 100 / enrichedRows.length

    return {
      ...row,
      width: Math.max(8, width),
      startText: formatDateTime(row.start, '--'),
      endText: formatDateTime(row.end, '--')
    }
  })
})

const handleRecordFields = computed(() => [
  {
    key: 'status',
    label: '处理状态',
    value: alert.value.alert_status_text || formatAlertStatus(alert.value.alert_status),
    badge: true,
    tone: getStatusTone(alert.value.alert_status)
  },
  { key: 'handler', label: '处理人', value: displayValue(alert.value.handler_id || alert.value.handler) },
  { key: 'time', label: '处理时间', value: formatDateTime(alert.value.handle_time || alert.value.handled_at, '--') },
  {
    key: 'desc',
    label: '处理说明',
    value: displayValue(alert.value.handle_desc || alert.value.handle_note || alert.value.handle_remark || alert.value.remark)
  },
  { key: 'advice', label: '告警建议', value: displayValue(alert.value.alert_advice) }
])

onMounted(() => {
  initHandlerId()
  loadDiagnosis()
})

onBeforeUnmount(() => {
  window.clearTimeout(feedbackTimer)
})

watch(
  () => route.params.id,
  () => {
    diagnosis.value = null
    handleError.value = ''
    handleForm.handleNote = ''
    loadDiagnosis()
  }
)

async function loadDiagnosis() {
  if (!alertId.value) {
    errorMessage.value = '缺少告警ID'
    return
  }

  const currentRequestId = ++requestId
  loading.value = true
  errorMessage.value = ''

  try {
    const result = await getAlertDiagnosis(alertId.value)

    if (currentRequestId !== requestId) {
      return
    }

    diagnosis.value = normalizeDiagnosis(normalizePayload(result))
    initHandlerId()
  } catch (error) {
    if (currentRequestId !== requestId) {
      return
    }

    diagnosis.value = null
    errorMessage.value = error.message || '告警研判数据加载失败'
  } finally {
    if (currentRequestId === requestId) {
      loading.value = false
    }
  }
}

async function submitHandle(action) {
  if (handleSubmitting.value) {
    return
  }

  handleError.value = ''
  const nextStatus = resolveSubmitStatus(action)
  const validationMessage = validateHandleForm(nextStatus)

  if (validationMessage) {
    handleError.value = validationMessage
    return
  }

  handleSubmitting.value = true

  try {
    await updateAlertStatus(alertId.value, {
      alert_status: nextStatus,
      handler_id: Number(handleForm.handlerId),
      handle_note: handleForm.handleNote.trim()
    })
    showFeedback(nextStatus === 'resolved' ? '告警已标记为已处理' : '告警处置已保存')
    handleForm.handleNote = ''
    await loadDiagnosis()
  } catch (error) {
    handleError.value = error.message || '告警处置提交失败'
  } finally {
    handleSubmitting.value = false
  }
}

function resolveSubmitStatus(action) {
  if (action === 'processing') {
    return 'processing'
  }

  if (action === 'resolved') {
    return 'resolved'
  }

  const currentStatus = normalizeAlertStatusKey(alert.value.alert_status)
  return currentStatus === 'resolved' ? 'resolved' : 'processing'
}

function validateHandleForm(nextStatus) {
  const handlerIdText = String(handleForm.handlerId || '').trim()
  const handlerId = Number(handlerIdText)
  const handleNote = handleForm.handleNote.trim()

  if (!['processing', 'resolved'].includes(nextStatus)) {
    return '处理状态必须为处理中或已处理'
  }

  if (!handlerIdText) {
    return '处理人ID不能为空'
  }

  if (!Number.isInteger(handlerId) || handlerId <= 0) {
    return '处理人ID必须为正整数'
  }

  if (handleNote.length < 5) {
    return '处置说明至少需要5个字'
  }

  return ''
}

function initHandlerId() {
  const user = getStoredUser()
  const handlerId = user?.user_id || user?.id || user?.handler_id || alert.value.handler_id

  if (handlerId && !handleForm.handlerId) {
    handleForm.handlerId = String(handlerId)
  }
}

function normalizeDiagnosis(payload) {
  const source = payload && typeof payload === 'object' ? payload : {}

  return {
    alert: source.alert && typeof source.alert === 'object' ? source.alert : {},
    run_record: source.run_record && typeof source.run_record === 'object' ? source.run_record : {},
    representative_risk: source.representative_risk && typeof source.representative_risk === 'object'
      ? source.representative_risk
      : {},
    monitor_series: normalizeRows(source.monitor_series),
    risk_series: normalizeRows(source.risk_series),
    health_series: normalizeRows(source.health_series),
    condition_segments: normalizeRows(source.condition_segments),
    diagnosis_summary: source.diagnosis_summary && typeof source.diagnosis_summary === 'object'
      ? source.diagnosis_summary
      : {}
  }
}

function normalizePayload(result) {
  if (!result || typeof result !== 'object') {
    return {}
  }

  return 'data' in result ? result.data || {} : result
}

function normalizeRows(value) {
  return Array.isArray(value) ? value.filter((row) => row && typeof row === 'object') : []
}

function sampleRows(rows, maxCount) {
  if (rows.length <= maxCount) {
    return rows
  }

  const step = Math.ceil(rows.length / maxCount)
  return rows.filter((_, index) => index % step === 0)
}

function isEventPoint(point) {
  const eventTime = normalizeTime(summary.value.event_time)
  const pointTime = normalizeTime(point.time || point.window_end_time || point.sample_time)
  return Boolean(eventTime && pointTime && eventTime === pointTime)
}

function isFocusCondition(label) {
  return Boolean(label && focusConditionLabel.value && String(label) === String(focusConditionLabel.value))
}

function showFeedback(message, tone = 'success') {
  feedbackMessage.value = message
  feedbackTone.value = tone
  window.clearTimeout(feedbackTimer)
  feedbackTimer = window.setTimeout(() => {
    feedbackMessage.value = ''
  }, 2600)
}

function getRiskTone(level) {
  const normalizedLevel = String(level || '').toLowerCase()

  if (normalizedLevel === 'high' || normalizedLevel === 'critical') {
    return 'danger'
  }

  if (normalizedLevel === 'medium' || normalizedLevel === 'warning') {
    return 'warning'
  }

  if (normalizedLevel === 'low' || normalizedLevel === 'info') {
    return 'success'
  }

  return 'muted'
}

function getStatusTone(status) {
  const normalizedStatus = normalizeAlertStatusKey(status)

  if (normalizedStatus === 'unhandled') {
    return 'danger'
  }

  if (normalizedStatus === 'processing') {
    return 'warning'
  }

  if (normalizedStatus === 'resolved') {
    return 'success'
  }

  return 'muted'
}

function normalizeAlertStatusKey(status) {
  const normalizedStatus = String(status || '').trim().toLowerCase()
  return normalizedStatus === 'pending' ? 'unhandled' : normalizedStatus
}

function getRiskDescription(level) {
  const tone = getRiskTone(level)
  if (tone === 'danger') return '高风险'
  if (tone === 'warning') return '需关注'
  if (tone === 'success') return '低风险'
  return '风险等级'
}

function getSegmentTone(index) {
  return ['primary', 'warning', 'success', 'info', 'muted'][index % 5]
}

function getDurationMs(start, end) {
  const startMs = Date.parse(start)
  const endMs = Date.parse(end)
  return Number.isFinite(startMs) && Number.isFinite(endMs) && endMs > startMs ? endMs - startMs : 0
}

function normalizeTime(value) {
  return displayText(value, '').replace('T', ' ').slice(0, 19)
}

function formatAxisTime(value) {
  const text = formatDateTime(value, '')
  return text ? text.slice(11, 19) || text : ''
}

function formatRiskScore(value) {
  return formatPercent(value, 2, '--')
}

function formatInteger(value) {
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? '--' : Math.round(numericValue).toLocaleString('zh-CN')
}

function toNumber(value) {
  return toFiniteNumber(value) ?? 0
}

function displayValue(value) {
  return displayText(value, '--')
}
</script>

<style scoped>
.alert-diagnosis-page {
  width: 100%;
  max-width: var(--layout-page-max);
  margin: 0 auto;
  display: grid;
  gap: var(--space-6);
}

.diagnosis-overview,
.diagnosis-summary-panel,
.diagnosis-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-sm);
}

.diagnosis-overview,
.diagnosis-panel {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-5);
}

.diagnosis-section-title h3,
.panel-heading h3,
.diagnosis-summary-copy h3 {
  margin: 4px 0 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.overview-info-grid {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(240px, 1fr) minmax(360px, 1.35fr);
  gap: var(--space-6);
  align-items: stretch;
}

.overview-info-list,
.handle-record-list,
.position-summary {
  display: grid;
  gap: var(--space-3);
  margin: 0;
}

.overview-info-list div,
.handle-record-list div,
.position-summary div {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: center;
}

.overview-info-list dt,
.handle-record-list dt,
.position-summary dt {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 760;
}

.overview-info-list dd,
.handle-record-list dd,
.position-summary dd {
  min-width: 0;
  margin: 0;
  color: var(--color-text-primary);
  font-weight: 760;
  overflow-wrap: anywhere;
}

.overview-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.overview-metric {
  display: grid;
  gap: var(--space-2);
  min-height: 132px;
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.overview-metric span,
.overview-metric small,
.diagnosis-summary-metrics span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 760;
}

.overview-metric strong {
  align-self: end;
  color: var(--color-text-primary);
  font-size: 1.8rem;
  line-height: 1;
}

.overview-metric--danger {
  border-color: var(--color-danger-border);
  background: var(--color-danger-soft);
}

.overview-metric--success {
  border-color: var(--color-success-border);
  background: var(--color-success-soft);
}

.overview-metric--primary {
  border-color: var(--color-info-border);
  background: var(--color-info-soft);
}

.diagnosis-summary-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(420px, 1fr);
  gap: var(--space-6);
  padding: var(--space-5);
}

.diagnosis-summary-copy p:last-child {
  margin: var(--space-4) 0 0;
  color: var(--color-text-secondary);
  line-height: 1.8;
}

.diagnosis-summary-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-3);
}

.diagnosis-summary-metrics article {
  display: grid;
  gap: var(--space-2);
  align-content: center;
  min-height: 84px;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.diagnosis-summary-metrics strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  overflow-wrap: anywhere;
}

.trend-grid,
.handle-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.event-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: #fff;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 760;
  white-space: nowrap;
}

.trend-event-note {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  margin: -6px 0 0;
  padding: 7px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: #fff;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 760;
}

.trend-event-note::before {
  width: 8px;
  height: 8px;
  margin-right: 7px;
  border-radius: 50%;
  content: "";
}

.trend-event-note--risk::before {
  background: var(--color-danger);
}

.trend-event-note--health::before {
  background: var(--color-success);
}

.monitor-tabs {
  display: inline-flex;
  width: fit-content;
  padding: 4px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.monitor-tab {
  min-height: 32px;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-weight: 760;
  cursor: pointer;
}

.monitor-tab--active {
  background: var(--color-primary);
  color: var(--color-text-inverse);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.18);
}

.position-analysis-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(220px, 0.6fr);
  gap: var(--space-5);
  align-items: start;
}

.position-summary {
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.condition-timeline {
  display: grid;
  gap: var(--space-4);
}

.condition-timeline__bar {
  display: flex;
  min-height: 48px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.condition-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 92px;
  padding: 0 var(--space-3);
  border-right: 1px solid rgba(255, 255, 255, 0.8);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 820;
  text-align: center;
}

.condition-segment:last-child {
  border-right: 0;
}

.condition-segment--primary {
  background: rgba(37, 99, 235, 0.18);
}

.condition-segment--warning {
  background: rgba(217, 119, 6, 0.2);
}

.condition-segment--success {
  background: rgba(22, 163, 74, 0.18);
}

.condition-segment--info {
  background: rgba(14, 165, 233, 0.16);
}

.condition-segment--muted {
  background: var(--color-neutral-soft);
}

.condition-segment--active {
  background: rgba(249, 115, 22, 0.9);
  color: #fff;
}

.condition-timeline__legend {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.condition-timeline__legend article {
  display: grid;
  grid-template-columns: auto minmax(0, auto) minmax(0, 1fr);
  gap: var(--space-2);
  align-items: center;
  min-width: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.condition-timeline__legend strong {
  color: var(--color-text-primary);
}

.condition-timeline__legend small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.condition-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-primary);
}

.condition-dot--warning {
  background: var(--color-warning);
}

.condition-dot--success {
  background: var(--color-success);
}

.condition-dot--info {
  background: #0ea5e9;
}

.condition-dot--muted {
  background: var(--color-text-muted);
}

.handle-form {
  display: grid;
  gap: var(--space-4);
}

.handle-field {
  display: grid;
  gap: var(--space-2);
}

.handle-field span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 760;
}

.handle-field strong {
  color: var(--color-danger);
}

.handle-field textarea,
.handle-field input {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
  color: var(--color-text-primary);
  outline: none;
}

.handle-field textarea {
  min-height: 108px;
  padding: var(--space-4);
  resize: vertical;
}

.handle-field input {
  min-height: 42px;
  padding: 0 var(--space-4);
}

.handle-field small {
  justify-self: end;
  color: var(--color-text-muted);
}

.handle-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.handle-actions__resolved {
  border-color: var(--color-success-border);
  color: var(--color-success);
}

.handle-message {
  margin: 0;
}

.alert-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid transparent;
  border-radius: var(--radius-pill);
  font-size: var(--font-size-xs);
  font-weight: 780;
  white-space: nowrap;
}

.alert-badge--danger {
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border-color: var(--color-danger-border);
}

.alert-badge--warning {
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border-color: var(--color-warning-border);
}

.alert-badge--success {
  color: var(--color-success);
  background: var(--color-success-soft);
  border-color: var(--color-success-border);
}

.alert-badge--muted {
  color: var(--color-text-muted);
  background: var(--color-neutral-soft);
  border-color: var(--color-neutral-border);
}

@media (max-width: 1280px) {
  .overview-info-grid,
  .diagnosis-summary-panel,
  .position-analysis-grid {
    grid-template-columns: 1fr;
  }

  .diagnosis-summary-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .trend-grid,
  .handle-grid,
  .overview-metric-grid,
  .condition-timeline__legend {
    grid-template-columns: 1fr;
  }

  .panel-heading,
  .handle-actions {
    display: grid;
  }
}

@media (max-width: 640px) {
  .diagnosis-summary-metrics,
  .overview-info-list div,
  .handle-record-list div,
  .position-summary div {
    grid-template-columns: 1fr;
  }

  .monitor-tabs {
    width: 100%;
  }

  .monitor-tab {
    flex: 1;
    padding: 0 var(--space-2);
  }
}
</style>
