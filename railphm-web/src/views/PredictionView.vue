<template>
  <section class="prediction-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">风险预测</p>
        <h2>设备故障风险趋势</h2>
        <p class="page-description">
          支持查询已持久化风险结果，并可基于 InfluxDB 监测数据触发区间滚动推理生成风险曲线。
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
          <h3>历史结果查询</h3>
          <p>按设备编号和时间范围查询服务端已持久化的风险结果，用于刷新历史趋势。</p>
        </div>
      </div>

      <div class="monitor-filter-grid prediction-filter-grid">
        <label class="filter-field">
          <span>设备编号</span>
          <input v-model.trim="filters.deviceId" type="text" placeholder="ATP001" :disabled="queryLoading" />
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
        <div class="latest-card-header-actions">
          <p>当前展示最新一次已落库风险结果，默认折叠以突出区间推理主流程。</p>
          <button
            type="button"
            class="secondary-button compact-toggle-button"
            @click="showLatestCard = !showLatestCard"
          >
            {{ showLatestCard ? '收起最新结果' : '展开最新结果' }}
          </button>
        </div>
      </div>

      <div class="prediction-panel__meta">
        <span class="device-chip">设备编号 {{ currentDeviceDisplay }}</span>
        <span :class="['status-pill', `status-pill--${latestRiskMeta.tone}`]">{{ latestRiskMeta.label }}</span>
        <span v-if="latestRecord && !showLatestCard" class="latest-compact-text">
          最新风险 {{ formatPercent(latestRecord.risk_score, 2) }}，
          健康度 {{ formatScore(latestRecord.health_score, 2) }}，
          窗口结束 {{ formatDateTime(latestRecord.window_end_time || latestRecord.ts_end) }}
        </span>
      </div>

      <div
        v-if="!latestRecord && !queryLoading && !queryErrors.latest && hasLoaded"
        class="state-panel empty-state"
      >
        当前设备暂无最新风险结果。
      </div>

      <div
        v-else-if="latestRecord && showLatestCard"
        class="monitor-overview-grid prediction-overview-grid"
      >
        <article class="monitor-overview-card">
          <span>设备编号</span>
          <strong>{{ displayText(latestRecord.device_code || latestRecord.device_id) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>风险分数</span>
          <strong>{{ formatPercent(latestRecord.risk_score, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>健康度</span>
          <strong>{{ formatScore(latestRecord.health_score, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>健康等级</span>
          <strong>{{ displayText(latestRecord.health_level || latestRecord.health_status) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>风险波动</span>
          <strong>{{ formatPercent(latestRecord.risk_std, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>原始风险</span>
          <strong>{{ formatPercent(latestRecord.risk_raw, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>工况标签</span>
          <strong>{{ displayText(latestRecord.condition_label) }}</strong>
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
          description="展示指定设备在查询时间范围内的真实风险分数变化。"
          metric-name="风险分数"
          :points="riskTrendPoints"
          :tooltip-details="historyTooltipDetails"
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
          :tooltip-details="historyTooltipDetails"
          :loading="queryLoading"
          :error="queryErrors.history"
          height="320px"
        />
      </div>
    </section>

    <section class="prediction-infer-card">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">区间滚动推理</p>
          <h3>生成区间风险曲线</h3>
        </div>
        <p>模型窗口大小固定采用训练参数 30 个连续监测点，本页面仅控制展示范围和区间推理输出步长。</p>
      </div>

      <form class="prediction-infer-form" @submit.prevent="handleRangeInfer">
        <div class="range-infer-grid">
          <label class="filter-field">
            <span>设备编号</span>
            <input
              v-model.trim="rangeInferForm.deviceCode"
              type="text"
              placeholder="ATP001"
              :disabled="rangeInferLoading"
            />
          </label>

          <label class="filter-field">
            <span>预测结束时间</span>
            <input
              v-model.trim="rangeInferForm.endTime"
              type="text"
              placeholder="2026-05-18 10:00:00"
              :disabled="rangeInferLoading"
            />
          </label>

          <label class="filter-field">
            <span>回看时长（分钟）</span>
            <input
              v-model.trim="rangeInferForm.lookbackMinutes"
              type="text"
              placeholder="60"
              :disabled="rangeInferLoading"
            />
          </label>

          <label class="filter-field">
            <span>推理步长（秒）</span>
            <input
              v-model.trim="rangeInferForm.inferenceStrideSeconds"
              type="text"
              placeholder="60"
              :disabled="rangeInferLoading"
            />
          </label>

          <label class="filter-field">
            <span>MC 采样次数</span>
            <input
              v-model.trim="rangeInferForm.mcSamples"
              type="text"
              placeholder="20"
              :disabled="rangeInferLoading"
            />
          </label>

          <div class="filter-field range-checkbox-field">
            <span>保存结果</span>
            <label class="checkbox-control">
              <input v-model="rangeInferForm.persist" type="checkbox" :disabled="rangeInferLoading" />
              <span>写入风险结果库</span>
            </label>
          </div>
        </div>

        <div class="action-bar prediction-infer-form__actions">
          <button type="submit" class="primary-button" :disabled="rangeInferLoading">
            {{ rangeInferLoading ? '推理中...' : '生成区间风险曲线' }}
          </button>
        </div>
      </form>

      <div v-if="rangeInferLoading" class="state-panel loading-state">
        正在执行区间滚动推理，请稍候...
      </div>

      <div v-if="rangeInferError" class="state-panel error-state">
        {{ rangeInferError }}
      </div>

      <div v-if="rangeInferSuccessMessage" class="state-panel success-state">
        {{ rangeInferSuccessMessage }}
      </div>

      <div
        v-if="!rangeInferLoading && !rangeInferError && !rangeInferResult"
        class="state-panel empty-state"
      >
        当前尚未生成区间风险曲线。后端会查询 InfluxDB 监测数据并调用 AI 完成滚动推理。
      </div>

      <div v-else-if="rangeInferResult" class="prediction-infer-result">
        <div class="range-summary-grid">
          <article v-for="card in rangeSummaryCards" :key="card.key" class="monitor-overview-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </article>
        </div>

        <div v-if="rangeResultEmptyMessage" class="state-panel empty-state">
          {{ rangeResultEmptyMessage }}
        </div>

        <div class="range-chart-grid">
          <MetricTrendChart
            title="本次风险分数曲线"
            description="来源于本次区间推理返回的 risk_series。"
            metric-name="风险分数"
            :points="rangeRiskTrendPoints"
            :tooltip-details="rangeRiskTooltipDetails"
            :loading="rangeInferLoading"
            :error="rangeInferError"
            height="300px"
          />

          <MetricTrendChart
            title="本次健康度曲线"
            description="优先使用本次区间推理返回的 health_series。"
            metric-name="健康度"
            unit=""
            :points="rangeHealthTrendPoints"
            :tooltip-details="rangeHealthTooltipDetails"
            :loading="rangeInferLoading"
            :error="rangeInferError"
            height="300px"
          />
        </div>

        <div v-if="rangeSkippedWindows.length" class="range-skipped-panel">
          <strong>跳过窗口 {{ rangeSkippedWindows.length }} 个</strong>
          <ul>
            <li v-for="item in rangeSkippedPreview" :key="`${item.time}-${item.reason}`">
              {{ displayText(item.time) }}：{{ displayText(item.reason) }}
            </li>
          </ul>
        </div>

        <div class="range-detail-block">
          <div class="range-detail-header">
            <div>
              <h4>本次推理结果明细</h4>
              <p v-if="rangeDetailOverflow">当前仅展示前 100 条，完整数据已用于曲线绘制。</p>
            </div>
          </div>

          <div v-if="rangeDetailRows.length" class="range-detail-table-wrap">
            <table class="range-detail-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>风险分数</th>
                  <th>风险标准差</th>
                  <th>原始风险</th>
                  <th>阈值</th>
                  <th>预测标签</th>
                  <th>健康度</th>
                  <th>健康等级</th>
                  <th>工况标签</th>
                  <th>窗口开始</th>
                  <th>窗口结束</th>
                  <th>风险结果ID</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rangeDetailRows" :key="row.key">
                  <td>{{ formatDateTime(row.time) }}</td>
                  <td>{{ formatPercent(row.risk_score, 2) }}</td>
                  <td>{{ formatPercent(row.risk_std, 2) }}</td>
                  <td>{{ formatPercent(row.risk_raw, 2) }}</td>
                  <td>{{ formatPercent(row.threshold, 2) }}</td>
                  <td>{{ displayText(row.predicted_label) }}</td>
                  <td>{{ formatScore(row.health_score, 2) }}</td>
                  <td>{{ displayText(row.health_level || row.health_status) }}</td>
                  <td>{{ displayText(row.condition_label) }}</td>
                  <td>{{ formatDateTime(row.window_start_time) }}</td>
                  <td>{{ formatDateTime(row.window_end_time) }}</td>
                  <td>{{ displayText(row.risk_result_id) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="state-panel empty-state">
            当前时间范围内未生成有效风险点，请检查监测数据连续性或调整结束时间。
          </div>
        </div>
      </div>
    </section>

    <section class="prediction-infer-card prediction-debug-card">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">高级调试</p>
          <h3>单点推理调试</h3>
        </div>
        <p>保留原单点推理入口用于调试，本页主功能为区间滚动推理。</p>
      </div>

      <form class="prediction-infer-form" @submit.prevent="handleInfer">
        <div class="prediction-infer-grid">
          <label class="filter-field">
            <span>设备编号</span>
            <input v-model.trim="inferForm.deviceId" type="text" placeholder="ATP001" :disabled="inferLoading" />
          </label>

          <label class="filter-field">
            <span>ts_end</span>
            <input
              v-model.trim="inferForm.tsEnd"
              type="text"
              placeholder="2026-05-18 10:05:00"
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
          <button type="submit" class="secondary-button" :disabled="inferLoading">
            {{ inferLoading ? '推理中...' : '触发单点推理' }}
          </button>
        </div>
      </form>

      <div v-if="inferLoading" class="state-panel loading-state">
        正在触发单点风险推理...
      </div>

      <div v-if="inferError" class="state-panel error-state">
        {{ inferError }}
      </div>

      <div v-if="inferResult" class="prediction-infer-result">
        <div class="prediction-panel__meta">
          <span class="device-chip">设备编号 {{ displayText(inferResult.device_code || inferResult.device_id) }}</span>
          <span :class="['status-pill', `status-pill--${inferAlertMeta.tone}`]">{{ inferAlertMeta.label }}</span>
          <span class="status-pill status-pill--default">{{ displayText(inferResult.condition_label) }}</span>
        </div>

        <div class="monitor-overview-grid prediction-overview-grid">
          <article class="monitor-overview-card">
            <span>风险分数</span>
            <strong>{{ formatPercent(inferResult.risk_score, 2) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>健康度</span>
            <strong>{{ formatScore(inferResult.health_score, 2) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>健康等级</span>
            <strong>{{ displayText(inferResult.health_level || inferResult.health_status) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>风险波动</span>
            <strong>{{ formatPercent(inferResult.risk_std, 2) }}</strong>
          </article>
          <article class="monitor-overview-card">
            <span>模型名称</span>
            <strong>{{ displayText(inferResult.model_name) }}</strong>
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

        <div class="prediction-detail-groups">
          <div v-for="group in inferDetailGroups" :key="group.title" class="prediction-detail-group">
            <h4>{{ group.title }}</h4>
            <dl class="prediction-detail-grid">
              <div v-for="field in group.fields" :key="field.key">
                <dt>{{ field.label }}</dt>
                <dd>{{ field.value }}</dd>
              </div>
            </dl>
          </div>
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
  inferPrediction,
  inferPredictionRange
} from '../api/prediction'
import { getRiskLevelMeta } from '../utils/dashboard'
import {
  displayText,
  formatAlertLevel,
  formatBoolean,
  formatCalibrationMethod,
  formatDataSource,
  formatDateTime,
  formatPercent,
  formatScore,
  formatUncertaintyMethod,
  toFiniteNumber
} from '../utils/formatters'

const route = useRoute()

const DEFAULT_FILTERS = {
  deviceId: 'ATP001',
  startTime: '2026-05-18 10:00:00',
  endTime: '2026-05-18 10:10:00'
}

const DEFAULT_INFER_FORM = {
  deviceId: DEFAULT_FILTERS.deviceId,
  tsEnd: '2026-05-18 10:05:00',
  windowMinutes: '5'
}

const DEFAULT_RANGE_INFER_FORM = {
  deviceCode: DEFAULT_FILTERS.deviceId,
  endTime: '2026-05-18 10:00:00',
  lookbackMinutes: '60',
  inferenceStrideSeconds: '60',
  mcSamples: '20',
  persist: true
}

const queryDeviceId = normalizeQueryDeviceId(route.query.device_code || route.query.device_id)
const filters = reactive({
  ...DEFAULT_FILTERS,
  deviceId: queryDeviceId || DEFAULT_FILTERS.deviceId
})
const inferForm = reactive({
  ...DEFAULT_INFER_FORM,
  deviceId: filters.deviceId
})
const rangeInferForm = reactive({
  ...DEFAULT_RANGE_INFER_FORM,
  deviceCode: filters.deviceId
})

const queryLoading = ref(false)
const validationMessage = ref('')
const hasLoaded = ref(false)
const showLatestCard = ref(false)
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
const rangeInferLoading = ref(false)
const rangeInferError = ref('')
const rangeInferResult = ref(null)

const hasPredictionData = computed(() => Boolean(latestRecord.value) || historyRecords.value.length > 0)
const latestRiskMeta = computed(() => getRiskLevelMeta(latestRecord.value?.health_score))
const currentDeviceDisplay = computed(
  () => displayText(latestRecord.value?.device_code || latestRecord.value?.device_id || historyMeta.value.device_id || filters.deviceId)
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

const historyTooltipDetails = computed(() =>
  historyRecords.value.map((item) => [
    { label: '原始风险', value: formatPercent(item.risk_raw, 2) },
    { label: '风险波动', value: formatPercent(item.risk_std, 2) },
    { label: '健康等级', value: displayText(item.health_level || item.health_status) },
    { label: '工况标签', value: displayText(item.condition_label) },
    { label: '模型版本', value: displayText(item.model_version) }
  ])
)

const rangeRiskSeries = computed(() =>
  Array.isArray(rangeInferResult.value?.risk_series) ? rangeInferResult.value.risk_series : []
)

const rangeHealthSeries = computed(() =>
  Array.isArray(rangeInferResult.value?.health_series) ? rangeInferResult.value.health_series : []
)

const rangeSkippedWindows = computed(() =>
  Array.isArray(rangeInferResult.value?.skipped_windows) ? rangeInferResult.value.skipped_windows : []
)

const rangeRiskTrendPoints = computed(() =>
  rangeRiskSeries.value.map((item) => ({
    time: getRangePointTime(item),
    value: item.risk_score
  }))
)

const rangeHealthTrendPoints = computed(() => {
  const healthSource = rangeHealthSeries.value.length ? rangeHealthSeries.value : rangeRiskSeries.value

  return healthSource.map((item) => ({
    time: getRangePointTime(item),
    value: item.health_score
  }))
})

const rangeRiskTooltipDetails = computed(() =>
  rangeRiskSeries.value.map((item) => [
    { label: '原始风险', value: formatPercent(item.risk_raw, 2) },
    { label: '风险标准差', value: formatPercent(item.risk_std, 2) },
    { label: '阈值', value: formatPercent(item.threshold, 2) },
    { label: '健康度', value: formatScore(item.health_score, 2) },
    { label: '工况标签', value: displayText(item.condition_label) }
  ])
)

const rangeHealthTooltipDetails = computed(() => {
  const riskByTime = new Map(rangeRiskSeries.value.map((item) => [getRangePointTime(item), item]))

  return rangeHealthTrendPoints.value.map((point) => {
    const riskItem = riskByTime.get(point.time)
    return [
      { label: '健康等级', value: displayText(riskItem?.health_level || riskItem?.health_status) },
      { label: '风险分数', value: formatPercent(riskItem?.risk_score, 2) },
      { label: '窗口结束', value: formatDateTime(riskItem?.window_end_time || point.time) }
    ]
  })
})

const rangeSummaryCards = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return []
  }

  return [
    { key: 'device_code', label: '设备编号', value: displayText(result.device_code) },
    { key: 'start_time', label: '开始时间', value: formatDateTime(result.start_time) },
    { key: 'end_time', label: '结束时间', value: formatDateTime(result.end_time) },
    { key: 'monitor_point_count', label: '查询监测点数', value: formatInteger(result.monitor_point_count) },
    { key: 'total_candidate_points', label: '候选风险点', value: formatInteger(result.total_candidate_points) },
    { key: 'result_count', label: '成功生成点', value: formatInteger(result.result_count) },
    { key: 'saved_count', label: '保存数量', value: formatInteger(result.saved_count) },
    { key: 'skipped_existing_count', label: '重复跳过', value: formatInteger(result.skipped_existing_count) },
    { key: 'skipped_window_count', label: '数据不足跳过', value: formatInteger(result.skipped_window_count) },
    { key: 'model_version', label: '模型版本', value: displayText(result.model_version) },
    { key: 'calibration_method', label: '校准方法', value: formatCalibrationMethod(result.calibration_method) },
    { key: 'uncertainty_method', label: '不确定性方法', value: formatUncertaintyMethod(result.uncertainty_method) }
  ]
})

const rangeDetailRows = computed(() => rangeRiskSeries.value.slice(0, 100))
const rangeDetailOverflow = computed(() => rangeRiskSeries.value.length > 100)
const rangeSkippedPreview = computed(() => rangeSkippedWindows.value.slice(0, 5))
const rangeResultEmptyMessage = computed(() => {
  if (!rangeInferResult.value || rangeInferLoading.value || rangeInferError.value) {
    return ''
  }

  return rangeRiskSeries.value.length === 0
    ? '当前时间范围内未生成有效风险点，请检查监测数据连续性或调整结束时间。'
    : ''
})

const rangeInferSuccessMessage = computed(() => {
  const result = rangeInferResult.value
  if (!result || rangeInferLoading.value || rangeInferError.value) {
    return ''
  }

  return `本次区间推理完成，共生成 ${formatInteger(result.result_count)} 个风险点，保存 ${formatInteger(result.saved_count)} 个，重复跳过 ${formatInteger(result.skipped_existing_count)} 个。`
})

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
    return '区间推理已接入'
  }

  return '区间推理已接入'
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
    return `当前设备 ${currentDeviceDisplay.value} 已返回 ${historyRecords.value.length} 个历史点位`
  }

  return '区间推理已接入，可按设备编号生成滚动风险曲线'
})

const inferAlertMeta = computed(() => {
  const alertLevel = String(inferResult.value?.alert_level || '').toLowerCase()

  if (alertLevel === 'high' || alertLevel === 'critical') {
    return {
      label: formatAlertLevel(alertLevel),
      tone: 'danger'
    }
  }

  if (alertLevel === 'medium' || alertLevel === 'warning') {
    return {
      label: formatAlertLevel(alertLevel),
      tone: 'warning'
    }
  }

  if (alertLevel === 'low' || alertLevel === 'info') {
    return {
      label: formatAlertLevel(alertLevel),
      tone: 'success'
    }
  }

  return {
    label: '结果待解释',
    tone: 'default'
  }
})

const inferDetailGroups = computed(() => {
  const record = inferResult.value
  if (!record) {
    return []
  }

  return [
    {
      title: '结果详情',
      fields: [
        { key: 'risk_result_id', label: '风险结果ID', value: displayText(record.risk_result_id) },
        { key: 'sample_index', label: '样本索引', value: displayText(record.sample_index) },
        { key: 'risk_raw', label: '原始风险', value: formatPercent(record.risk_raw, 2) },
        { key: 'risk_raw_std', label: '原始风险波动', value: formatPercent(record.risk_raw_std, 2) },
        { key: 'threshold', label: '阈值', value: formatPercent(record.threshold, 2) },
        { key: 'predicted_label', label: '预测标签', value: displayText(record.predicted_label) }
      ]
    },
    {
      title: '模型与数据',
      fields: [
        { key: 'model_name', label: '模型名称', value: displayText(record.model_name) },
        { key: 'model_version', label: '模型版本', value: displayText(record.model_version) },
        { key: 'data_source', label: '数据来源', value: formatDataSource(record.data_source) },
        { key: 'condition_label', label: '工况标签', value: displayText(record.condition_label) }
      ]
    },
    {
      title: '校准与不确定性',
      fields: [
        { key: 'calibration_enabled', label: '启用校准', value: formatBoolean(record.calibration_enabled) },
        { key: 'calibration_method', label: '校准方法', value: formatCalibrationMethod(record.calibration_method) },
        { key: 'uncertainty_enabled', label: '启用不确定性', value: formatBoolean(record.uncertainty_enabled) },
        { key: 'uncertainty_method', label: '不确定性方法', value: formatUncertaintyMethod(record.uncertainty_method) },
        { key: 'mc_samples', label: 'MC 样本数', value: displayText(record.mc_samples) },
        { key: 'risk_std', label: '风险标准差', value: formatPercent(record.risk_std, 2) }
      ]
    },
    {
      title: '时间窗口',
      fields: [
        { key: 'window_start_time', label: '窗口开始时间', value: formatDateTime(record.window_start_time) },
        { key: 'window_end_time', label: '窗口结束时间', value: formatDateTime(record.window_end_time) },
        { key: 'ts_end', label: 'ts_end', value: formatDateTime(record.ts_end) },
        { key: 'window_minutes', label: '窗口分钟数', value: displayText(record.window_minutes) }
      ]
    }
  ]
})

watch(
  () => filters.deviceId,
  (deviceId) => {
    inferForm.deviceId = deviceId || DEFAULT_FILTERS.deviceId
    rangeInferForm.deviceCode = deviceId || DEFAULT_FILTERS.deviceId
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
  Object.assign(rangeInferForm, DEFAULT_RANGE_INFER_FORM)
  inferError.value = ''
  inferResult.value = null
  rangeInferError.value = ''
  rangeInferResult.value = null
  await fetchPredictionData()
}

async function handleRangeInfer() {
  const message = validateRangeInferForm()

  if (message) {
    rangeInferError.value = message
    rangeInferResult.value = null
    return
  }

  rangeInferLoading.value = true
  rangeInferError.value = ''
  rangeInferResult.value = null

  try {
    const result = await inferPredictionRange(buildRangeInferPayload())
    rangeInferResult.value = normalizeRangeInferResult(normalizePayload(result))

    if (rangeInferForm.persist) {
      filters.deviceId = rangeInferResult.value?.device_code || rangeInferForm.deviceCode
      filters.startTime = rangeInferResult.value?.start_time || filters.startTime
      filters.endTime = rangeInferResult.value?.end_time || filters.endTime
      await fetchPredictionData()
    }
  } catch (error) {
    rangeInferError.value = error.message || '区间滚动推理失败，请稍后重试'
  } finally {
    rangeInferLoading.value = false
  }
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
    await fetchPredictionData()
  } catch (error) {
    inferError.value = error.message || '风险推理失败，请稍后重试'
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
    return '风险推理的设备编号不能为空'
  }

  if (!inferForm.tsEnd) {
    return '风险推理的 ts_end 不能为空'
  }

  if (!inferForm.windowMinutes) {
    return '风险推理的 window_minutes 不能为空'
  }

  const windowMinutes = Number.parseInt(inferForm.windowMinutes, 10)
  if (!Number.isFinite(windowMinutes) || windowMinutes <= 0) {
    return '风险推理的 window_minutes 必须为正整数'
  }

  return ''
}

function validateRangeInferForm() {
  if (!rangeInferForm.deviceCode) {
    return '区间推理的设备编号不能为空'
  }

  if (!rangeInferForm.endTime) {
    return '区间推理的预测结束时间不能为空'
  }

  const lookbackMinutes = parsePositiveInteger(rangeInferForm.lookbackMinutes)
  if (lookbackMinutes === null) {
    return '回看时长必须为正整数'
  }

  if (lookbackMinutes > 180) {
    return '回看时长过大，建议不超过 180 分钟'
  }

  const inferenceStrideSeconds = parsePositiveInteger(rangeInferForm.inferenceStrideSeconds)
  if (inferenceStrideSeconds === null) {
    return '推理步长必须为正整数'
  }

  if (inferenceStrideSeconds < 10) {
    return '步长过小可能导致推理时间较长，请使用不少于 10 秒的推理步长'
  }

  const mcSamples = parsePositiveInteger(rangeInferForm.mcSamples)
  if (mcSamples === null) {
    return 'MC 采样次数必须为正整数'
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

function buildRangeInferPayload() {
  return {
    device_code: rangeInferForm.deviceCode,
    end_time: rangeInferForm.endTime,
    lookback_minutes: Number.parseInt(rangeInferForm.lookbackMinutes, 10),
    inference_stride_seconds: Number.parseInt(rangeInferForm.inferenceStrideSeconds, 10),
    mc_samples: Number.parseInt(rangeInferForm.mcSamples, 10),
    persist: Boolean(rangeInferForm.persist)
  }
}

function normalizePayload(result) {
  let payload = result

  if (payload && typeof payload === 'object' && 'code' in payload && payload.data == null) {
    return null
  }

  while (
    payload &&
    typeof payload === 'object' &&
    payload.data &&
    typeof payload.data === 'object' &&
    payload.data !== payload
  ) {
    payload = payload.data
  }

  return payload
}

function normalizeLatest(record) {
  if (!record || typeof record !== 'object') {
    return null
  }

  return {
    risk_result_id: record.risk_result_id ?? null,
    device_id: record.device_id ?? null,
    device_code: record.device_code || '',
    sample_index: record.sample_index ?? null,
    ts_end: record.ts_end || '',
    window_minutes: toFiniteNumber(record.window_minutes),
    risk_raw: toFiniteNumber(record.risk_raw),
    risk_score: getRiskScore(record),
    risk_raw_std: toFiniteNumber(record.risk_raw_std),
    health_score: toFiniteNumber(record.health_score),
    health_level: record.health_level || '',
    health_status: record.health_status || '',
    risk_std: toFiniteNumber(record.risk_std),
    threshold: toFiniteNumber(record.threshold),
    predicted_label: record.predicted_label ?? '',
    alert_generated: Boolean(record.alert_generated),
    alert_level: record.alert_level || '',
    alert_status: record.alert_status || '',
    alert_status_text: record.alert_status_text || '',
    alert_message: record.alert_message || '',
    alert_advice: record.alert_advice || '',
    alert_id: record.alert_id ?? '',
    condition_label: record.condition_label || '',
    model_name: record.model_name || '',
    model_version: record.model_version || '',
    calibration_enabled: record.calibration_enabled,
    calibration_method: record.calibration_method || '',
    uncertainty_enabled: record.uncertainty_enabled,
    uncertainty_method: record.uncertainty_method || '',
    mc_samples: record.mc_samples ?? '',
    data_source: record.data_source || '',
    window_start_time: record.window_start_time || '',
    window_end_time: record.window_end_time || '',
    created_at: record.created_at || ''
  }
}

function normalizeHistory(records) {
  const sourceRecords = extractHistoryRecords(records)

  return sourceRecords
    .map((item) => normalizeLatest(item))
    .filter((item) => item && (item.window_end_time || item.window_start_time))
    .sort((a, b) => getRecordTime(a).localeCompare(getRecordTime(b)))
}

function normalizeRangeInferResult(record) {
  if (!record || typeof record !== 'object') {
    return null
  }

  const riskSeries = Array.isArray(record.risk_series)
    ? record.risk_series.map((item, index) => normalizeRangeRiskPoint(item, index))
    : []
  const healthSeries = Array.isArray(record.health_series)
    ? record.health_series.map((item, index) => normalizeRangeHealthPoint(item, index))
    : []

  return {
    device_code: record.device_code || '',
    start_time: record.start_time || '',
    end_time: record.end_time || '',
    lookback_minutes: toFiniteNumber(record.lookback_minutes),
    inference_stride_seconds: toFiniteNumber(record.inference_stride_seconds),
    mc_samples: toFiniteNumber(record.mc_samples),
    monitor_query_start_time: record.monitor_query_start_time || '',
    monitor_point_count: toFiniteNumber(record.monitor_point_count),
    total_candidate_points: toFiniteNumber(record.total_candidate_points),
    result_count: toFiniteNumber(record.result_count),
    saved_count: toFiniteNumber(record.saved_count),
    skipped_existing_count: toFiniteNumber(record.skipped_existing_count),
    skipped_window_count: toFiniteNumber(record.skipped_window_count),
    model_name: record.model_name || '',
    model_version: record.model_version || '',
    calibration_enabled: record.calibration_enabled,
    calibration_method: record.calibration_method || '',
    uncertainty_enabled: record.uncertainty_enabled,
    uncertainty_method: record.uncertainty_method || '',
    risk_series: riskSeries,
    health_series: healthSeries,
    skipped_windows: Array.isArray(record.skipped_windows) ? record.skipped_windows : []
  }
}

function normalizeRangeRiskPoint(item, index) {
  const source = item && typeof item === 'object' ? item : {}
  const time = source.time || source.window_end_time || ''

  return {
    key: `${time}-${source.risk_result_id ?? index}`,
    risk_result_id: source.risk_result_id ?? null,
    time,
    window_start_time: source.window_start_time || '',
    window_end_time: source.window_end_time || '',
    risk_raw: toFiniteNumber(source.risk_raw),
    risk_score: getRiskScore(source),
    risk_raw_std: toFiniteNumber(source.risk_raw_std),
    risk_std: toFiniteNumber(source.risk_std),
    threshold: toFiniteNumber(source.threshold),
    predicted_label: source.predicted_label ?? '',
    health_score: toFiniteNumber(source.health_score),
    health_level: source.health_level || '',
    health_status: source.health_status || '',
    condition_label: source.condition_label || ''
  }
}

function normalizeRangeHealthPoint(item, index) {
  const source = item && typeof item === 'object' ? item : {}
  const time = source.time || source.window_end_time || ''

  return {
    key: `${time}-${index}`,
    time,
    window_end_time: source.window_end_time || '',
    health_score: toFiniteNumber(source.health_score),
    health_level: source.health_level || '',
    health_status: source.health_status || ''
  }
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

function getRecordTime(record) {
  return record?.window_end_time || record?.created_at || record?.window_start_time || ''
}

function getRangePointTime(record) {
  return record?.time || record?.window_end_time || record?.window_start_time || ''
}

function parsePositiveInteger(value) {
  const parsedValue = Number.parseInt(value, 10)
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : null
}

function formatInteger(value) {
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? displayText(null) : Math.trunc(numericValue).toLocaleString('zh-CN')
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

.latest-card-header-actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
  text-align: right;
}

.latest-card-header-actions p {
  max-width: 560px;
}

.compact-toggle-button {
  min-height: 36px;
  padding: 0 14px;
}

.latest-compact-text {
  color: var(--rail-text-muted);
  font-weight: 720;
  line-height: 1.6;
}

.prediction-overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.prediction-chart-grid,
.prediction-infer-grid,
.range-infer-grid,
.range-summary-grid,
.range-chart-grid {
  display: grid;
  gap: var(--rail-gap-lg);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.prediction-infer-grid {
  grid-template-columns: minmax(140px, 0.65fr) minmax(260px, 1fr) minmax(140px, 0.5fr);
}

.range-infer-grid {
  grid-template-columns: minmax(150px, 0.75fr) minmax(250px, 1.15fr) repeat(4, minmax(130px, 0.65fr));
}

.range-summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.range-chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.range-checkbox-field {
  align-content: start;
}

.checkbox-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  color: var(--rail-text-strong);
  font-weight: 720;
}

.checkbox-control input {
  width: 16px !important;
  height: 16px !important;
  min-height: 16px !important;
  padding: 0 !important;
  border-radius: 4px !important;
  accent-color: var(--rail-brand);
}

.checkbox-control span {
  color: var(--rail-text-strong);
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

.range-skipped-panel {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid rgba(217, 119, 6, 0.28);
  border-radius: var(--rail-radius-md);
  background: rgba(255, 251, 235, 0.78);
  color: var(--rail-text);
}

.range-skipped-panel strong {
  color: var(--rail-text-strong);
}

.range-skipped-panel ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 20px;
}

.range-detail-block {
  display: grid;
  gap: 12px;
}

.range-detail-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.range-detail-header h4,
.range-detail-header p {
  margin: 0;
}

.range-detail-header h4 {
  color: var(--rail-text-strong);
}

.range-detail-header p {
  margin-top: 6px;
  color: var(--rail-text-muted);
  line-height: 1.6;
}

.range-detail-table-wrap {
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-md);
  background: rgba(255, 255, 255, 0.74);
}

.range-detail-table {
  width: 100%;
  min-width: 1180px;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.range-detail-table th,
.range-detail-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--rail-border);
  text-align: left;
  white-space: nowrap;
}

.range-detail-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(248, 250, 252, 0.96);
  color: var(--rail-text-muted);
  font-weight: 760;
}

.range-detail-table td {
  color: var(--rail-text);
}

.success-state {
  border-color: rgba(22, 163, 74, 0.24);
  background: rgba(240, 253, 244, 0.8);
  color: #166534;
}

.prediction-debug-card {
  background: rgba(255, 255, 255, 0.62);
}

.prediction-detail-groups {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.prediction-detail-group {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-md);
  background: rgba(255, 255, 255, 0.62);
}

.prediction-detail-group h4 {
  margin: 0;
  color: var(--rail-text-strong);
}

.prediction-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.prediction-detail-grid div {
  min-width: 0;
}

.prediction-detail-grid dt,
.prediction-detail-grid dd {
  margin: 0;
}

.prediction-detail-grid dt {
  color: var(--rail-text-muted);
  font-size: 0.86rem;
  font-weight: 700;
}

.prediction-detail-grid dd {
  margin-top: 6px;
  color: var(--rail-text-strong);
  font-weight: 760;
  overflow-wrap: anywhere;
}

@media (max-width: 1180px) {
  .prediction-overview-grid,
  .prediction-chart-grid,
  .range-summary-grid,
  .range-chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .range-infer-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
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
  .prediction-infer-grid,
  .range-infer-grid,
  .range-summary-grid,
  .range-chart-grid,
  .prediction-detail-groups,
  .prediction-detail-grid {
    grid-template-columns: 1fr;
  }

  .prediction-panel__meta {
    align-items: flex-start;
  }

  .latest-card-header-actions {
    justify-content: flex-start;
    text-align: left;
  }
}
</style>
