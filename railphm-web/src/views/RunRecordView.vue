<template>
  <section class="run-record-page">
    <div class="monitor-topbar run-record-hero">
      <div class="monitor-topbar__content">
        <p class="page-tag">运行记录</p>
        <h2>运行记录池</h2>
        <p class="page-description">
          每条运行记录对应一个连续的 source_segment，用于监控展示与按秒风险推断。
        </p>
      </div>

      <div class="monitor-topbar__meta">
        <span :class="['status-pill', `status-pill--${statusTone}`]">{{ statusLabel }}</span>
        <span class="monitor-topbar__summary">{{ statusDescription }}</span>
      </div>
      <div class="run-record-hero__rail" aria-hidden="true">
        <span></span>
      </div>
    </div>

    <div class="monitor-overview-grid run-record-stat-grid">
      <article
        v-for="card in summaryCards"
        :key="card.key"
        :class="['monitor-overview-card', 'run-record-stat-card', `run-record-stat-card--${card.tone}`]"
      >
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.description }}</small>
      </article>
    </div>

    <form class="monitor-filter-card run-record-filter-card" @submit.prevent="handleSearch">
      <div class="monitor-filter-card__header">
        <div>
          <h3>筛选条件</h3>
          <p>按设备编号、运行记录状态和分页大小筛选片段池。</p>
        </div>
      </div>

      <div class="monitor-filter-grid run-record-filter-grid">
        <label class="filter-field">
          <span>设备编号</span>
          <select v-model="filters.device_code" :disabled="loading">
            <option value="">全部设备</option>
            <option value="ATP001">ATP001</option>
            <option value="ATP002">ATP002</option>
            <option value="ATP003">ATP003</option>
          </select>
        </label>

        <label class="filter-field">
          <span>状态</span>
          <select v-model="filters.status" :disabled="loading">
            <option value="">全部状态</option>
            <option value="ready">ready - 未分析</option>
            <option value="inferred">inferred - 已预测</option>
            <option value="alerted">alerted - 已告警</option>
          </select>
        </label>

        <label class="filter-field">
          <span>每页数量</span>
          <select v-model.number="filters.page_size" :disabled="loading">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </label>

        <div class="action-bar run-record-filter-actions">
          <button type="submit" class="primary-button" :disabled="loading">
            {{ loading ? '加载中...' : '刷新列表' }}
          </button>
          <button type="button" class="secondary-button" :disabled="randomLoading" @click="handleRandom">
            {{ randomLoading ? '选择中...' : '随机选择' }}
          </button>
        </div>
      </div>
    </form>

    <div v-if="feedbackMessage" :class="['state-panel', feedbackToneClass]">
      {{ feedbackMessage }}
    </div>

    <div v-if="loading" class="state-panel loading-state">正在加载运行记录...</div>
    <div v-if="errorMessage" class="state-panel error-state">运行记录加载失败：{{ errorMessage }}</div>
    <div v-if="!loading && !errorMessage && records.length === 0" class="state-panel empty-state">
      当前筛选条件下暂无运行记录。
    </div>

    <section class="monitor-section run-record-table-card">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">片段池</p>
          <h3>运行记录列表</h3>
        </div>
        <p>展示当前筛选条件下的运行记录，支持查看详情并进入预测工作台。</p>
      </div>

      <div class="run-record-table-wrapper">
        <table class="run-record-table">
          <thead>
            <tr>
              <th>运行记录编号</th>
              <th>设备编号</th>
              <th>source_segment</th>
              <th>开始时间</th>
              <th>结束时间</th>
              <th>点数</th>
              <th>持续时长</th>
              <th>状态</th>
              <th>最高风险</th>
              <th>最高风险等级</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in records" :key="record.run_record_id">
              <td class="record-code-cell">{{ displayText(record.run_record_code, '--') }}</td>
              <td>{{ displayText(record.device_code, '--') }}</td>
              <td class="segment-cell" :title="record.source_segment">{{ displayText(record.source_segment, '--') }}</td>
              <td>{{ formatDateTime(record.record_start_time, '--') }}</td>
              <td>{{ formatDateTime(record.record_end_time, '--') }}</td>
              <td>{{ formatInteger(record.point_count) }}</td>
              <td>{{ formatDuration(record.duration_seconds) }}</td>
              <td><span :class="['record-tag', `record-tag--${getStatusTone(record.status)}`]">{{ formatRunRecordStatus(record.status) }}</span></td>
              <td>{{ formatPercent(record.max_risk_score, 2, '--') }}</td>
              <td><span :class="['record-tag', `record-tag--${getRiskTone(record.max_alert_level)}`]">{{ formatRunRecordRisk(record.max_alert_level) }}</span></td>
              <td>
                <div class="table-actions">
                  <RouterLink class="secondary-button table-action-button" :to="{ name: 'run-record-detail', params: { id: record.run_record_id } }">
                    查看详情
                  </RouterLink>
                  <RouterLink
                    class="primary-button table-action-button"
                    :to="{ name: 'run-record-detail', params: { id: record.run_record_id }, query: { action: 'predict' } }"
                  >
                    进入预测
                  </RouterLink>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="run-record-pagination">
        <span>第 {{ filters.page }} 页 / 共 {{ totalPages }} 页</span>
        <div class="page-actions">
          <button type="button" class="secondary-button" :disabled="filters.page <= 1 || loading" @click="goPage(filters.page - 1)">
            上一页
          </button>
          <button type="button" class="secondary-button" :disabled="filters.page >= totalPages || loading" @click="goPage(filters.page + 1)">
            下一页
          </button>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import {
  getRandomRunRecord,
  getRunRecords
} from '../api/runRecord'
import {
  displayText,
  formatDateTime,
  formatPercent,
  toFiniteNumber
} from '../utils/formatters'

const router = useRouter()

const filters = reactive({
  page: 1,
  page_size: 10,
  device_code: '',
  status: ''
})
const records = ref([])
const total = ref(0)
const listSummary = ref(null)
const loading = ref(false)
const randomLoading = ref(false)
const errorMessage = ref('')
const feedbackMessage = ref('')
const feedbackTone = ref('success')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / filters.page_size)))
const pageRecordCount = computed(() => toSummaryNumber('page_record_count', records.value.length))
const totalRecordCount = computed(() => toSummaryNumber('total_record_count', total.value))
const inferredCount = computed(() => toSummaryNumber(
  'inferred_count',
  records.value.filter((record) => isInferredRecord(record)).length
))
const riskSegmentCount = computed(() => toSummaryNumber(
  'risk_segment_count',
  records.value.filter((record) => isRiskSegmentLevel(record.max_alert_level)).length
))
const summaryCards = computed(() => [
  {
    key: 'page',
    label: '当前页记录数',
    value: formatInteger(pageRecordCount.value),
    description: '当前页返回',
    tone: 'primary'
  },
  {
    key: 'total',
    label: '记录总数',
    value: formatInteger(totalRecordCount.value),
    description: '当前筛选条件',
    tone: 'default'
  },
  {
    key: 'inferred',
    label: '已推理',
    value: formatInteger(inferredCount.value),
    description: '已完成风险预测',
    tone: 'success'
  },
  {
    key: 'risk',
    label: '风险片段数',
    value: formatInteger(riskSegmentCount.value),
    description: '存在非正常最高风险',
    tone: 'danger'
  }
])
const statusTone = computed(() => {
  if (loading.value) return 'muted'
  if (errorMessage.value) return 'warning'
  if (records.value.length > 0) return 'success'
  return 'default'
})
const statusLabel = computed(() => {
  if (loading.value) return '记录加载中'
  if (errorMessage.value) return '加载异常'
  if (records.value.length > 0) return '运行记录已接入'
  return '等待记录'
})
const statusDescription = computed(() => {
  if (loading.value) return '正在请求 /api/v1/run-records'
  if (errorMessage.value) return '请检查后端服务或接口代理配置'
  return `当前筛选返回 ${pageRecordCount.value} 条，共 ${totalRecordCount.value} 条`
})
const feedbackToneClass = computed(() => (feedbackTone.value === 'error' ? 'error-state' : 'success-state'))

onMounted(() => {
  fetchRecords()
})

watch(
  () => [filters.page_size, filters.device_code, filters.status],
  () => {
    filters.page = 1
  }
)

async function fetchRecords() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await getRunRecords(buildParams())
    const payload = normalizePayload(result)
    records.value = Array.isArray(payload.items) ? payload.items : []
    total.value = Number(payload.total) || 0
    listSummary.value = payload.summary && typeof payload.summary === 'object' ? payload.summary : null
  } catch (error) {
    records.value = []
    total.value = 0
    listSummary.value = null
    errorMessage.value = error.message || '无法加载运行记录'
  } finally {
    loading.value = false
  }
}

function buildParams() {
  return {
    page: filters.page,
    page_size: filters.page_size,
    device_code: filters.device_code || undefined,
    status: filters.status || undefined
  }
}

function handleSearch() {
  filters.page = 1
  fetchRecords()
}

async function handleRandom() {
  randomLoading.value = true
  clearFeedback()
  try {
    const result = await getRandomRunRecord({
      device_code: filters.device_code || undefined
    })
    const record = normalizePayload(result)
    if (record?.run_record_id) {
      router.push({ name: 'run-record-detail', params: { id: record.run_record_id } })
    } else {
      showFeedback('未找到可用运行记录', 'error')
    }
  } catch (error) {
    showFeedback(error.message || '随机选择失败', 'error')
  } finally {
    randomLoading.value = false
  }
}

function goPage(page) {
  filters.page = Math.min(Math.max(1, page), totalPages.value)
  fetchRecords()
}

function normalizePayload(result) {
  return result?.data && typeof result.data === 'object' ? result.data : result
}

function toSummaryNumber(key, fallback) {
  const value = listSummary.value?.[key]
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? fallback : numericValue
}

function isInferredRecord(record) {
  const status = String(record?.status || '').toLowerCase()
  return status === 'inferred' || status === 'alerted' || Boolean(record?.max_risk_result_id)
}

function isRiskSegmentLevel(level) {
  return ['low', 'attention', 'medium', 'warning', 'warn', 'high', 'critical'].includes(
    String(level || '').trim().toLowerCase()
  )
}

function showFeedback(message, tone = 'success') {
  feedbackMessage.value = message
  feedbackTone.value = tone
}

function clearFeedback() {
  feedbackMessage.value = ''
  feedbackTone.value = 'success'
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

function getStatusTone(status) {
  if (status === 'alerted') return 'danger'
  if (status === 'inferred') return 'warning'
  if (status === 'ready') return 'muted'
  return 'default'
}

function getRiskTone(level) {
  const normalized = String(level || '').toLowerCase()
  if (normalized === 'high' || normalized === 'critical') return 'danger'
  if (normalized === 'medium' || normalized === 'warning' || normalized === 'warn') return 'warning'
  if (normalized === 'low' || normalized === 'attention') return 'notice'
  return 'success'
}
</script>

<style scoped>
.run-record-page {
  width: 100%;
  max-width: var(--layout-page-max);
  margin: 0 auto;
  display: grid;
  gap: var(--space-6);
}

.run-record-hero {
  position: relative;
  overflow: hidden;
  min-height: 170px;
}

.run-record-hero__rail {
  position: absolute;
  right: 28px;
  bottom: 22px;
  width: min(360px, 34vw);
  height: 86px;
  opacity: 0.34;
  pointer-events: none;
}

.run-record-hero__rail::before,
.run-record-hero__rail::after,
.run-record-hero__rail span {
  position: absolute;
  content: "";
}

.run-record-hero__rail::before {
  inset: 18px 0 24px 28px;
  border: 2px solid rgba(37, 99, 235, 0.48);
  border-left-width: 8px;
  border-radius: 999px 22px 22px 999px;
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.1), rgba(37, 99, 235, 0.02));
}

.run-record-hero__rail::after {
  right: 28px;
  bottom: 13px;
  width: 210px;
  height: 2px;
  background: rgba(37, 99, 235, 0.38);
  box-shadow: -64px 14px 0 rgba(37, 99, 235, 0.18);
}

.run-record-hero__rail span {
  right: 62px;
  top: 32px;
  width: 88px;
  height: 12px;
  border-radius: 999px;
  background: repeating-linear-gradient(
    90deg,
    rgba(37, 99, 235, 0.55) 0 14px,
    rgba(37, 99, 235, 0.18) 14px 22px
  );
}

.run-record-stat-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.run-record-stat-card {
  position: relative;
  overflow: hidden;
}

.run-record-stat-card::before {
  position: absolute;
  top: 24px;
  right: 22px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-info-soft);
  content: "";
}

.run-record-stat-card small {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: 650;
}

.run-record-stat-card--danger {
  border-color: var(--color-danger-border);
}

.run-record-stat-card--danger::before {
  background: var(--color-danger-soft);
}

.run-record-stat-card--success::before {
  background: var(--color-success-soft);
}

.run-record-filter-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
}

.run-record-filter-actions {
  align-self: end;
}

.run-record-table-card {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
}

.run-record-table-wrapper {
  min-width: 0;
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.run-record-table {
  width: 100%;
  min-width: 1180px;
  border-collapse: collapse;
}

.run-record-table th,
.run-record-table td {
  padding: 13px 12px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  vertical-align: middle;
}

.run-record-table th {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 760;
  background: var(--color-bg-panel);
}

.run-record-table td {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}

.record-code-cell,
.segment-cell {
  max-width: 210px;
  overflow-wrap: anywhere;
}

.record-tag {
  display: inline-flex;
  align-items: center;
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

.record-tag--muted,
.record-tag--default {
  background: var(--color-neutral-soft);
}

.table-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.table-action-button {
  min-height: 32px;
  padding: 0 10px;
  font-size: var(--font-size-xs);
}

.run-record-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  color: var(--color-text-secondary);
  font-weight: 680;
}

@media (max-width: 980px) {
  .run-record-stat-grid {
    grid-template-columns: 1fr;
  }

  .run-record-filter-grid {
    grid-template-columns: 1fr;
  }

  .run-record-filter-actions {
    justify-content: flex-start;
  }
}
</style>
