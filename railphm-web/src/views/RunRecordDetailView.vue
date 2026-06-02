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

    <section class="monitor-section detail-panel prediction-status-panel">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">预测任务状态</p>
          <h3>{{ predictionStatusTitle }}</h3>
        </div>
        <p>{{ predictionStatusDescription }}</p>
      </div>

      <div class="prediction-progress-card">
        <div class="prediction-progress-card__main">
          <strong>{{ predictionStage }}</strong>
          <span>{{ predictionProgress }}%</span>
          <div class="prediction-progress-bar" aria-hidden="true">
            <span :style="{ width: `${predictionProgress}%` }"></span>
          </div>
          <small>已耗时 {{ predictionElapsedSeconds }}s</small>
        </div>

        <div class="prediction-stepper">
          <div
            v-for="step in predictionSteps"
            :key="step.key"
            :class="['prediction-step', getPredictionStepClass(step)]"
          >
            <span>{{ step.index }}</span>
            <strong>{{ step.label }}</strong>
            <small>{{ getPredictionStepText(step) }}</small>
          </div>
        </div>
      </div>

      <div v-if="riskResult" class="risk-result-summary prediction-result-summary">
        <article v-for="card in inferSummaryCards" :key="card.key" class="monitor-overview-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
        </article>
      </div>
      <div v-else-if="inferError" class="state-panel error-state">
        逐秒风险预测失败：{{ inferError }}
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
          unit="%"
          :points="healthTrendPoints"
          :tooltip-details="healthTooltipDetails"
          :loading="inferLoading"
          :error="inferError"
          height="330px"
        />
      </div>

    </section>

    <section class="monitor-section detail-panel">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">运行监测分析</p>
          <h3>原始 1 秒采样监测数据</h3>
        </div>
        <p>当前返回 {{ monitorRows.length }} 个监测点，数据按 source_segment 边界查询。</p>
      </div>

      <div class="monitor-tabs" role="tablist" aria-label="运行监测分析">
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
        title="速度与制动"
        description="展示 speed、service_brake_speed 与 emergency_brake_speed 的运行变化。"
        :x-axis-data="monitorXAxis"
        :series="monitorSpeedSeries"
        :loading="monitorLoading"
        :empty="monitorRows.length === 0"
        :error="monitorError"
        height="360px"
      />

      <div v-else-if="activeMonitorTab === 'environment'" class="detail-chart-grid">
        <LineTrendChart
          title="环境温度"
          description="展示 outdoor_temperature 随时间变化。"
          :x-axis-data="monitorXAxis"
          :series="temperatureSeries"
          :loading="monitorLoading"
          :empty="monitorRows.length === 0"
          :error="monitorError"
          height="300px"
        />
        <LineTrendChart
          title="环境湿度"
          description="展示 humidity 随时间变化。"
          :x-axis-data="monitorXAxis"
          :series="humiditySeries"
          :loading="monitorLoading"
          :empty="monitorRows.length === 0"
          :error="monitorError"
          height="300px"
        />
      </div>

      <div v-else class="detail-chart-grid">
        <LineTrendChart
          title="里程"
          description="里程表示列车在线路坐标体系下的绝对位置，单位为 km。"
          unit="km"
          :x-axis-data="monitorXAxis"
          :series="mileageSeries"
          :loading="monitorLoading"
          :empty="monitorRows.length === 0"
          :error="monitorError"
          height="300px"
        />

        <LineTrendChart
          title="运行距离"
          description="运行距离表示当前 source_segment 片段内从起点开始累计行驶的相对距离，单位为 km。"
          unit="km"
          :x-axis-data="monitorXAxis"
          :series="runDistanceSeries"
          :loading="monitorLoading"
          :empty="monitorRows.length === 0"
          :error="monitorError"
          height="300px"
        />
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

        <div v-if="conditionSegments.length" class="condition-timeline">
          <div class="condition-timeline__bar">
            <article
              v-for="(segment, index) in conditionSegments"
              :key="segment.key"
              :class="['condition-segment', `condition-segment--${getSegmentTone(index)}`, { 'condition-segment--active': isFocusSegment(segment) }]"
              :style="{ flexBasis: `${segment.width}%` }"
              :title="formatConditionSegmentTitle(segment)"
            >
              {{ displayText(segment.label, '--') }}
            </article>
          </div>
          <div class="condition-timeline__legend">
            <article v-for="(segment, index) in conditionSegments" :key="`${segment.key}-legend`">
              <span :class="['condition-dot', `condition-dot--${getSegmentTone(index)}`]" aria-hidden="true"></span>
              <strong>{{ displayText(segment.label, '--') }}</strong>
              <small>
                {{ formatDateTime(segment.start, '--') }} ~ {{ formatDateTime(segment.end, '--') }} / {{ segment.count }} 点
                <template v-if="segment.smoothAppliedCount"> / 平滑 {{ segment.smoothAppliedCount }} 点</template>
              </small>
            </article>
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
              <dd>{{ formatHealthScore(alertResult.health_score, 2, '--') }}</dd>
            </div>
            <div>
              <dt>创建状态</dt>
              <dd>{{ formatAlertCreateState(alertResult) }}</dd>
            </div>
          </dl>
          <button
            v-if="alertResult.alert_id"
            class="primary-button alert-diagnosis-link"
            type="button"
            @click="goAlertDiagnosis"
          >
            查看告警研判详情
          </button>
        </div>
        <div v-else class="state-panel empty-state">
          预测达到告警阈值后，系统会提示是否生成正式告警。
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
              <td>{{ formatHealthScore(row.health_score, 2, '--') }}</td>
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

    <div v-if="inferLoading" class="modal-mask">
      <div class="modal-card prediction-modal-card" role="dialog" aria-modal="true">
        <div class="loading-ring" aria-hidden="true"></div>
        <h3>正在执行逐秒风险预测</h3>
        <p>系统正在处理当前运行片段，请勿重复点击</p>
        <div class="modal-progress">
          <div class="prediction-progress-bar" aria-hidden="true">
            <span :style="{ width: `${predictionProgress}%` }"></span>
          </div>
          <strong>{{ predictionProgress }}%</strong>
        </div>
        <p class="prediction-modal-stage">当前阶段：{{ predictionStage }}</p>
        <p class="prediction-modal-elapsed">已耗时 {{ predictionElapsedSeconds }}s</p>
        <div class="prediction-stepper prediction-stepper--modal">
          <div
            v-for="step in predictionSteps"
            :key="`modal-${step.key}`"
            :class="['prediction-step', getPredictionStepClass(step)]"
          >
            <span>{{ step.index }}</span>
            <strong>{{ step.label }}</strong>
            <small>{{ getPredictionStepText(step) }}</small>
          </div>
        </div>
        <button class="secondary-button modal-disabled-button" type="button" disabled>处理中...</button>
      </div>
    </div>

    <div v-if="alertConfirmVisible" class="modal-mask">
      <div class="modal-card alert-confirm-card" role="dialog" aria-modal="true">
        <h3>生成运行记录告警</h3>
        <p>检测到该运行记录存在较高风险点，系统可基于最高风险结果生成正式告警，并同步至告警中心。</p>
        <dl class="alert-confirm-grid">
          <div v-for="item in alertConfirmFields" :key="item.key">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
        <div v-if="alertError" class="state-panel error-state alert-modal-error">
          {{ alertError }}
        </div>
        <div class="modal-actions">
          <button class="secondary-button" type="button" :disabled="alertLoading" @click="handleCancelGenerateAlert">
            暂不生成
          </button>
          <button class="primary-button" type="button" :disabled="alertLoading" @click="handleConfirmGenerateAlert">
            {{ alertLoading ? '生成中...' : '生成告警' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="alertSuccessVisible" class="modal-mask">
      <div class="modal-card alert-success-card" role="dialog" aria-modal="true">
        <button class="modal-close-button" type="button" @click="closeAlertSuccessModal">×</button>
        <div class="success-check" aria-hidden="true"></div>
        <h3>{{ alertSuccessTitle }}</h3>
        <p>已同步至告警中心，可继续查看告警研判详情</p>
        <p class="alert-success-id">告警ID：<strong>{{ displayText(alertResult?.alert_id, '--') }}</strong></p>
        <div class="modal-actions">
          <button class="primary-button" type="button" :disabled="!alertResult?.alert_id" @click="goAlertDiagnosis">
            查看告警详情
          </button>
          <button class="secondary-button" type="button" @click="closeAlertSuccessModal">
            知道了
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
  formatHealthScore,
  formatPercent,
  toFiniteNumber
} from '../utils/formatters'
import { DEFAULT_EMA_ALPHA, applyEmaToPoints } from '../utils/seriesSmoothing'

const DEFAULT_INFERENCE_STRIDE_SECONDS = 1
const RISK_TREND_EMA_ALPHA = DEFAULT_EMA_ALPHA

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
const activeMonitorTab = ref('speed')
const predictionState = ref('idle')
const predictionProgress = ref(0)
const predictionStage = ref('等待开始')
const predictionElapsedSeconds = ref(0)
const alertConfirmVisible = ref(false)
const alertSuccessVisible = ref(false)
const alertError = ref('')
const errorMessage = ref('')
const monitorError = ref('')
const inferError = ref('')
const feedbackMessage = ref('')
const feedbackTone = ref('success')
let predictionTimer = 0
let elapsedTimer = 0

const monitorTabs = [
  { key: 'speed', label: '速度与制动' },
  { key: 'environment', label: '环境与工况' },
  { key: 'position', label: '位置与运行' }
]
const predictionSteps = [
  { key: 'read', index: 1, label: '读取监测数据', progress: 8 },
  { key: 'window', index: 2, label: '构建滑动窗口', progress: 32 },
  { key: 'infer', index: 3, label: '模型推理', progress: 58 },
  { key: 'save', index: 4, label: '保存预测结果', progress: 90 }
]

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
const mileageSeries = computed(() => [
  {
    name: '里程',
    unit: 'km',
    data: monitorRows.value.map((row) => toNumberOrNull(row.mileage)),
    area: true
  }
])
const runDistanceSeries = computed(() => [
  {
    name: '运行距离',
    unit: 'km',
    data: monitorRows.value.map((row) => toNumberOrNull(row.run_distance)),
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
const riskTrendSourceRows = computed(() =>
  riskSeries.value.filter((point) => {
    const time = point.time || point.window_end_time
    return time && toNumberOrNull(point.risk_score) !== null
  })
)
const rawRiskTrendPoints = computed(() =>
  riskTrendSourceRows.value.map((point) => ({
    time: point.time || point.window_end_time,
    value: toNumberOrNull(point.risk_score)
  }))
)
// EMA smoothing is only used for visualization.
// Raw risk_score and health_score are still used for alert rules, tables and persisted records.
const riskTrendPoints = computed(() => applyEmaToPoints(rawRiskTrendPoints.value, { alpha: RISK_TREND_EMA_ALPHA }))
const healthTrendSourceRows = computed(() =>
  healthSeries.value.filter((point) => {
    const time = point.time || point.window_end_time
    return time && toNumberOrNull(point.health_score) !== null
  })
)
const rawHealthTrendPoints = computed(() =>
  healthTrendSourceRows.value.map((point) => ({
    time: point.time || point.window_end_time,
    value: toNumberOrNull(point.health_score)
  }))
)
const healthTrendPoints = computed(() => applyEmaToPoints(rawHealthTrendPoints.value, { alpha: RISK_TREND_EMA_ALPHA }))
const riskTooltipDetails = computed(() =>
  riskTrendSourceRows.value.map((point) => [
    { label: '风险原始值', value: formatPercent(point.risk_score, 2, '--') },
    { label: '窗口结束', value: formatDateTime(point.window_end_time || point.time, '--') },
    { label: '风险波动', value: formatPercent(point.risk_std, 2, '--') },
    { label: '工况', value: displayText(point.condition_label, '--') },
    ...buildConditionTraceDetails(point),
    { label: '持久化', value: formatPersistStatus(point.persist_status) }
  ])
)
const healthTooltipDetails = computed(() =>
  healthTrendSourceRows.value.map((point) => [
    { label: '健康度原始值', value: formatHealthScore(point.health_score, 2, '--') },
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
    const trace = getConditionTrace(row)
    const rawLabel = trace.raw_condition_label_before_smooth || label
    const smoothApplied = Boolean(trace.condition_smooth_applied)
    if (!active || active.label !== label) {
      if (active) {
        segments.push(active)
      }
      active = {
        key: `${label}-${index}`,
        label,
        start: time,
        end: time,
        count: 1,
        smoothAppliedCount: smoothApplied ? 1 : 0,
        rawLabels: new Set(rawLabel ? [rawLabel] : [])
      }
    } else {
      active.end = time
      active.count += 1
      if (smoothApplied) {
        active.smoothAppliedCount += 1
      }
      if (rawLabel) {
        active.rawLabels.add(rawLabel)
      }
    }
  })
  if (active) segments.push(active)
  const limitedSegments = segments.slice(0, 18)
  const totalCount = limitedSegments.reduce((sum, segment) => sum + segment.count, 0)
  return limitedSegments.map((segment) => ({
    ...segment,
    rawLabelsText: Array.from(segment.rawLabels).join(' / '),
    width: totalCount > 0 ? Math.max(8, (segment.count / totalCount) * 100) : 100 / limitedSegments.length
  }))
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
  { key: 'level', label: '最高风险等级', value: formatRunRecordRisk(runRecord.value?.max_alert_level) }
])
const inferSummaryCards = computed(() => [
  { key: 'max', label: '最高风险分数', value: formatPercent(riskResult.value?.max_risk_score, 2, '--') },
  { key: 'level', label: '最高风险等级', value: formatRunRecordRisk(riskResult.value?.max_alert_level) },
  { key: 'result', label: '风险点数量', value: formatInteger(riskResult.value?.result_count) },
  { key: 'riskId', label: '代表风险结果ID', value: displayText(riskResult.value?.max_risk_result_id, '--') },
  { key: 'saved', label: '新保存', value: formatInteger(riskResult.value?.saved_count) },
  { key: 'existing', label: '复用已有', value: formatInteger(riskResult.value?.skipped_existing_count) },
  { key: 'recommend', label: '是否建议生成告警', value: riskResult.value?.alert_recommendation?.should_prompt ? '是' : '否' }
])
const feedbackToneClass = computed(() => (feedbackTone.value === 'error' ? 'error-state' : 'success-state'))
const predictionStatusTitle = computed(() => {
  if (predictionState.value === 'running') return '正在执行逐秒风险预测'
  if (predictionState.value === 'success') return '预测完成摘要'
  if (predictionState.value === 'error') return '预测失败'
  return '等待执行预测'
})
const predictionStatusDescription = computed(() => {
  if (predictionState.value === 'running') return '系统正在处理当前运行片段，请勿重复点击。'
  if (predictionState.value === 'success') return '已生成风险序列，可继续查看趋势并按建议生成告警。'
  if (predictionState.value === 'error') return '逐秒风险预测失败，可重新点击执行预测。'
  return '点击“执行逐秒预测”后，系统将按 1 秒步长对当前 source_segment 生成风险序列。'
})
const alertRecommendation = computed(() => riskResult.value?.alert_recommendation || null)
const alertConfirmFields = computed(() => [
  { key: 'risk', label: '最高风险分数', value: formatPercent(alertRecommendation.value?.max_risk_score, 2, '--') },
  { key: 'level', label: '最高风险等级', value: formatRunRecordRisk(alertRecommendation.value?.max_alert_level) },
  { key: 'riskId', label: '代表风险结果ID', value: displayText(alertRecommendation.value?.max_risk_result_id, '--') },
  { key: 'warning', label: '预警阈值', value: formatPercent(alertRecommendation.value?.warning_threshold, 0, '--') },
  { key: 'critical', label: '严重阈值', value: formatPercent(alertRecommendation.value?.critical_threshold, 0, '--') }
])
const alertSuccessTitle = computed(() => (alertResult.value?.existing ? '告警已存在' : '告警生成成功'))
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
  if (route.query.action === 'predict') {
    predictionState.value = 'idle'
    window.setTimeout(() => {
      document.querySelector('.prediction-status-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
  }
})

watch(
  () => route.params.id,
  () => {
    resetPredictionProgress()
    closeAlertModals()
    riskResult.value = null
    alertResult.value = null
    loadPage()
  }
)

onBeforeUnmount(() => {
  clearPredictionTimers()
})

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
  if (inferLoading.value) {
    return
  }

  inferLoading.value = true
  inferError.value = ''
  alertError.value = ''
  alertConfirmVisible.value = false
  alertSuccessVisible.value = false
  alertResult.value = null
  predictionState.value = 'running'
  startPredictionProgress()
  clearFeedback()
  try {
    const result = await inferRunRecord(runRecordId.value, {
      mc_samples: 20,
      persist: true,
      generate_alert: false,
      inference_stride_seconds: DEFAULT_INFERENCE_STRIDE_SECONDS
    })
    finishPredictionProgress()
    riskResult.value = normalizePayload(result)
    runRecord.value = {
      ...(runRecord.value || {}),
      status: riskResult.value.run_record_status || 'inferred',
      max_risk_score: riskResult.value.max_risk_score,
      max_risk_result_id: riskResult.value.max_risk_result_id,
      max_alert_level: riskResult.value.max_alert_level
    }
    predictionState.value = 'success'
    await wait(360)
    openAlertConfirmIfNeeded()
  } catch (error) {
    failPredictionProgress()
    inferError.value = error.message || '执行逐秒预测失败'
    predictionState.value = 'error'
    showFeedback(inferError.value, 'error')
  } finally {
    inferLoading.value = false
    clearPredictionTimers()
  }
}

async function handleConfirmGenerateAlert() {
  alertLoading.value = true
  alertError.value = ''
  try {
    const result = await generateRunRecordAlert(runRecordId.value, {})
    alertResult.value = normalizePayload(result)
    syncRunRecordAfterAlert()
    alertConfirmVisible.value = false
    if (alertResult.value.alert_generated) {
      openAlertSuccessModal()
    } else {
      showFeedback(alertResult.value.message || '最高风险未达到预警阈值，未生成正式告警')
    }
  } catch (error) {
    alertError.value = error.message || '生成运行记录告警失败'
  } finally {
    alertLoading.value = false
  }
}

function syncRunRecordAfterAlert() {
  if (!alertResult.value) {
    return
  }

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
}

function handleCancelGenerateAlert() {
  alertConfirmVisible.value = false
  showFeedback('已保留预测结果，可稍后生成告警。')
}

function openAlertConfirmIfNeeded() {
  const recommendation = riskResult.value?.alert_recommendation
  if (!recommendation) {
    showFeedback('预测完成')
    return
  }

  if (recommendation.should_prompt && recommendation.can_generate_alert) {
    alertConfirmVisible.value = true
    return
  }

  showFeedback(recommendation.message || '预测完成')
}

function openAlertSuccessModal() {
  alertSuccessVisible.value = true
}

function closeAlertSuccessModal() {
  alertSuccessVisible.value = false
}

function closeAlertModals() {
  alertConfirmVisible.value = false
  alertSuccessVisible.value = false
  alertError.value = ''
}

function goAlertDiagnosis() {
  if (alertResult.value?.alert_id) {
    router.push({ name: 'alert-diagnosis-detail', params: { id: alertResult.value.alert_id } })
    return
  }

  router.push({ name: 'alerts' })
}

function startPredictionProgress() {
  clearPredictionTimers()
  predictionProgress.value = 0
  predictionElapsedSeconds.value = 0
  predictionStage.value = getPredictionStage(0)
  predictionTimer = window.setInterval(() => {
    const nextProgress = Math.min(
      90,
      predictionProgress.value + (predictionProgress.value < 28 ? 6 : predictionProgress.value < 58 ? 4 : 2)
    )
    predictionProgress.value = nextProgress
    predictionStage.value = getPredictionStage(nextProgress)
  }, 700)
  elapsedTimer = window.setInterval(() => {
    predictionElapsedSeconds.value += 1
  }, 1000)
}

function finishPredictionProgress() {
  clearPredictionTimers()
  predictionProgress.value = 100
  predictionStage.value = '整理预测结果'
}

function failPredictionProgress() {
  clearPredictionTimers()
  predictionStage.value = '预测失败'
}

function resetPredictionProgress() {
  clearPredictionTimers()
  predictionState.value = 'idle'
  predictionProgress.value = 0
  predictionElapsedSeconds.value = 0
  predictionStage.value = '等待开始'
}

function clearPredictionTimers() {
  window.clearInterval(predictionTimer)
  window.clearInterval(elapsedTimer)
  predictionTimer = 0
  elapsedTimer = 0
}

function getPredictionStage(progress) {
  if (progress < 25) return '读取监测数据'
  if (progress < 50) return '构建滑动窗口'
  if (progress < 90) return '模型推理与结果保存'
  return '整理预测结果'
}

function getPredictionStepClass(step) {
  if (predictionProgress.value >= step.progress + 20 || predictionProgress.value === 100) {
    return 'prediction-step--done'
  }
  if (predictionProgress.value >= step.progress) {
    return 'prediction-step--active'
  }
  return 'prediction-step--pending'
}

function getPredictionStepText(step) {
  const className = getPredictionStepClass(step)
  if (className === 'prediction-step--done') return '已完成'
  if (className === 'prediction-step--active') return '进行中'
  return '待开始'
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
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
    critical: '严重',
    high: '严重',
    warning: '预警',
    warn: '预警',
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
  if (normalized === 'high' || normalized === 'critical') return 'danger'
  if (normalized === 'medium' || normalized === 'warning' || normalized === 'warn') return 'warning'
  if (normalized === 'low' || normalized === 'attention') return 'notice'
  return 'success'
}

function getSegmentTone(index) {
  return ['primary', 'warning', 'success', 'notice', 'muted'][index % 5]
}

function isFocusSegment(segment) {
  const focusLabel = riskRows.value[0]?.condition_label || riskSeries.value.find((row) => row.condition_label)?.condition_label
  return Boolean(focusLabel && segment?.label === focusLabel)
}

function getConditionTrace(point) {
  const trace = point?.trace
  return trace && typeof trace === 'object' && !Array.isArray(trace) ? trace : {}
}

function buildConditionTraceDetails(point) {
  const trace = getConditionTrace(point)
  const rawLabel = trace.raw_condition_label_before_smooth
  const reason = trace.condition_smooth_reason
  const details = []

  if (rawLabel && rawLabel !== point?.condition_label) {
    details.push({ label: '平滑前工况', value: displayText(rawLabel, '--') })
  }
  if (reason) {
    details.push({ label: '工况平滑原因', value: formatConditionSmoothReason(reason) })
  }

  return details
}

function formatConditionSmoothReason(reason) {
  const normalizedReason = reason === null || reason === undefined ? '' : String(reason).trim()
  const reasonMap = {
    confirmed_transition: '连续确认切换',
    short_segment_absorbed: '短片段吸收',
    cruise_sandwich_guard: '高速巡航扰动保护',
    terminal_segment_preserved: '边界片段保留',
    unchanged: '未调整'
  }

  return reasonMap[normalizedReason] || displayText(normalizedReason, '--')
}

function formatConditionSegmentTitle(segment) {
  if (!segment) {
    return ''
  }

  return [
    `主工况：${displayText(segment.label, '--')}`,
    `时间：${formatDateTime(segment.start, '--')} ~ ${formatDateTime(segment.end, '--')}`,
    `点数：${formatInteger(segment.count)}`,
    `平滑替换：${formatInteger(segment.smoothAppliedCount)}`,
    `原始标签：${displayText(segment.rawLabelsText, '--')}`
  ].join('\n')
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

.prediction-status-panel {
  border-color: rgba(37, 99, 235, 0.18);
}

.prediction-progress-card {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.prediction-progress-card__main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
}

.prediction-progress-card__main strong {
  color: var(--color-primary);
  font-size: var(--font-size-base);
}

.prediction-progress-card__main span {
  color: var(--color-text-primary);
  font-weight: 820;
}

.prediction-progress-card__main small {
  grid-column: 1 / -1;
  color: var(--color-text-muted);
  font-weight: 680;
}

.prediction-progress-bar {
  grid-column: 1 / -1;
  height: 9px;
  overflow: hidden;
  border-radius: var(--radius-pill);
  background: #e5eaf3;
}

.prediction-progress-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb 0%, #22c55e 100%);
  transition: width 0.35s ease;
}

.prediction-stepper {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.prediction-step {
  display: grid;
  justify-items: center;
  gap: var(--space-2);
  color: var(--color-text-muted);
  text-align: center;
}

.prediction-step span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: #fff;
  font-weight: 820;
}

.prediction-step strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}

.prediction-step small {
  font-size: var(--font-size-xs);
}

.prediction-step--done span {
  border-color: var(--color-success-border);
  background: var(--color-success);
  color: #fff;
}

.prediction-step--active span {
  border-color: rgba(37, 99, 235, 0.26);
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.12);
}

.prediction-step--active small {
  color: var(--color-primary);
  font-weight: 760;
}

.prediction-result-summary {
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  min-height: 34px;
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

.condition-timeline {
  display: grid;
  gap: var(--space-4);
}

.condition-timeline__bar {
  display: flex;
  min-height: 46px;
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
  border-right: 1px solid rgba(255, 255, 255, 0.86);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 820;
  text-align: center;
}

.condition-segment:last-child {
  border-right: 0;
}

.condition-segment--primary {
  background: rgba(37, 99, 235, 0.16);
}

.condition-segment--warning {
  background: rgba(217, 119, 6, 0.18);
}

.condition-segment--success {
  background: rgba(22, 163, 74, 0.17);
}

.condition-segment--notice {
  background: rgba(14, 165, 233, 0.14);
}

.condition-segment--muted {
  background: var(--color-neutral-soft);
}

.condition-segment--active {
  background: rgba(249, 115, 22, 0.86);
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
}

.condition-timeline__legend strong,
.condition-timeline__legend small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.condition-timeline__legend small {
  color: var(--color-text-muted);
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

.condition-dot--notice {
  background: #0ea5e9;
}

.condition-dot--muted {
  background: var(--color-text-muted);
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

.alert-diagnosis-link {
  justify-self: start;
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

.record-tag--primary {
  border-color: rgba(37, 99, 235, 0.22);
  background: rgba(37, 99, 235, 0.08);
  color: var(--color-primary);
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(3px);
}

.modal-card {
  width: min(620px, 100%);
  display: grid;
  justify-items: center;
  gap: var(--space-4);
  padding: 44px 48px 36px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.22);
  text-align: center;
}

.modal-card h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1.6rem;
}

.modal-card p {
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.loading-ring {
  width: 92px;
  height: 92px;
  border-radius: 50%;
  border: 8px solid rgba(34, 197, 94, 0.14);
  border-top-color: #22c55e;
  animation: prediction-spin 1s linear infinite;
}

@keyframes prediction-spin {
  to {
    transform: rotate(360deg);
  }
}

.modal-progress {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
}

.modal-progress .prediction-progress-bar {
  grid-column: auto;
}

.modal-progress strong {
  color: var(--color-success);
  font-weight: 820;
}

.prediction-modal-stage,
.prediction-modal-elapsed {
  color: var(--color-text-secondary);
  font-weight: 700;
}

.prediction-stepper--modal {
  width: 100%;
  margin-top: var(--space-2);
}

.modal-disabled-button {
  margin-top: var(--space-2);
  min-width: 138px;
}

.alert-confirm-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-3);
  margin: 0;
}

.alert-confirm-grid div {
  display: grid;
  gap: 5px;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.alert-confirm-grid dt {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 760;
}

.alert-confirm-grid dd {
  margin: 0;
  color: var(--color-text-primary);
  font-weight: 820;
}

.alert-modal-error {
  width: 100%;
  margin: 0;
  text-align: left;
}

.modal-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.modal-actions .primary-button,
.modal-actions .secondary-button {
  min-width: 142px;
}

.alert-success-card {
  position: relative;
  width: min(560px, 100%);
}

.modal-close-button {
  position: absolute;
  top: 20px;
  right: 22px;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 1.7rem;
  cursor: pointer;
}

.success-check {
  position: relative;
  width: 112px;
  height: 112px;
  border: 8px solid rgba(34, 197, 94, 0.18);
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.05);
}

.success-check::after {
  position: absolute;
  left: 31px;
  top: 34px;
  width: 44px;
  height: 24px;
  border-left: 8px solid #22a75a;
  border-bottom: 8px solid #22a75a;
  transform: rotate(-45deg);
  content: "";
}

.alert-success-id {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-secondary);
}

.alert-success-id strong {
  color: var(--color-primary);
}

@media (max-width: 1080px) {
  .detail-chart-grid,
  .detail-grid,
  .run-record-summary-grid,
  .risk-result-summary,
  .prediction-result-summary,
  .prediction-stepper,
  .condition-timeline__legend,
  .alert-confirm-grid {
    grid-template-columns: 1fr;
  }

  .condition-item {
    grid-template-columns: 1fr;
  }

  .modal-card {
    padding: 34px 24px 28px;
  }
}
</style>
