<template>
  <section class="alert-center-page">
    <PageHeader
      title="告警中心"
      eyebrow="告警中心"
      description="集中管理列控设备告警信息，支持告警查询、跟踪与处理。"
      :meta="headerMetaText"
    >
      <template #actions>
        <button class="secondary-button" type="button" :disabled="listLoading" @click="fetchAlerts">
          {{ listLoading ? '刷新中...' : '刷新' }}
        </button>
      </template>
    </PageHeader>

    <section class="alert-summary-grid" aria-label="当前页告警统计">
      <article
        v-for="card in alertSummaryCards"
        :key="card.key"
        :class="['alert-summary-card', `alert-summary-card--${card.tone}`]"
      >
        <div class="alert-summary-card__icon" aria-hidden="true">{{ card.icon }}</div>
        <div class="alert-summary-card__body">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.description }}</p>
        </div>
      </article>
    </section>

    <form class="alert-filter-bar" @submit.prevent="handleSearch">
      <label class="filter-field filter-field--device">
        <span>设备编号</span>
        <input
          v-model.trim="filters.deviceId"
          type="search"
          placeholder="请输入设备编号或ID"
          :disabled="listLoading"
        />
      </label>

      <label class="filter-field">
        <span>告警等级</span>
        <select v-model="filters.alertLevel" :disabled="listLoading">
          <option value="">全部</option>
          <option v-for="option in levelOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <label class="filter-field">
        <span>处理状态</span>
        <select v-model="filters.alertStatus" :disabled="listLoading">
          <option value="">全部</option>
          <option v-for="option in statusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <div class="filter-actions">
        <button class="primary-button" type="submit" :disabled="listLoading">
          查询
        </button>
        <button class="secondary-button" type="button" :disabled="listLoading" @click="handleReset">
          重置
        </button>
      </div>
    </form>

    <section class="alert-table-card">
      <header class="alert-table-card__header">
        <div>
          <p class="section-tag">告警列表</p>
          <h3>告警记录清单</h3>
        </div>
        <div class="alert-table-card__meta">
          <span>共 {{ pagination.total }} 条</span>
          <span>第 {{ pagination.page }} / {{ pageCount }} 页</span>
        </div>
      </header>

      <ErrorState
        v-if="listError"
        title="告警列表加载失败"
        :message="listError"
        retry-text="重新加载"
        @retry="fetchAlerts"
      />

      <div v-else class="alert-table-wrapper">
        <table class="alert-table">
          <thead>
            <tr>
              <th>告警ID</th>
              <th>设备编号</th>
              <th>告警等级</th>
              <th>处理状态</th>
              <th>风险分数</th>
              <th>健康度</th>
              <th>告警时间</th>
              <th>告警说明</th>
              <th class="alert-table__action-col">操作</th>
            </tr>
          </thead>

          <tbody v-if="listLoading">
            <tr>
              <td colspan="9">
                <LoadingBlock text="正在加载告警列表..." height="220px" />
              </td>
            </tr>
          </tbody>

          <tbody v-else-if="alertItems.length">
            <tr
              v-for="item in alertItems"
              :key="item.alert_id"
              :class="['alert-table__row', `alert-table__row--${getRiskTone(item.alert_level)}`]"
            >
              <td class="alert-table__mono">{{ displayValue(item.alert_id) }}</td>
              <td>{{ displayValue(item.device_code || item.device_id) }}</td>
              <td>
                <span :class="['alert-badge', `alert-badge--${getRiskTone(item.alert_level)}`]">
                  {{ formatAlertLevel(item.alert_level) }}
                </span>
              </td>
              <td>
                <span :class="['alert-badge', `alert-badge--${getStatusTone(item.alert_status)}`]">
                  {{ item.alert_status_text || formatAlertStatus(item.alert_status) }}
                </span>
              </td>
              <td :class="['alert-table__score', `alert-table__score--${getRiskTone(item.alert_level)}`]">
                {{ formatRiskScore(item.risk_score) }}
              </td>
              <td class="alert-table__score alert-table__score--health">
                {{ formatHealthScore(item.health_score, 2, '--') }}
              </td>
              <td class="alert-table__time">
                {{ formatDateTime(item.alert_time || item.created_at || item.updated_at, '--') }}
              </td>
              <td class="alert-table__message" :title="displayValue(item.alert_message || item.message)">
                {{ displayValue(item.alert_message || item.message) }}
              </td>
              <td class="alert-table__action-cell">
                <button class="secondary-button table-action-button" type="button" @click="goDiagnosis(item)">
                  查看详情
                </button>
                <button
                  class="primary-button table-action-button"
                  type="button"
                  :disabled="isResolved(item.alert_status)"
                  @click="goDiagnosis(item)"
                >
                  处理
                </button>
              </td>
            </tr>
          </tbody>

          <tbody v-else>
            <tr>
              <td colspan="9">
                <EmptyState
                  :title="emptyTitle"
                  description="可调整筛选条件后重新查询。"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="alert-pagination">
        <p>{{ rangeText }}</p>
        <div class="alert-pagination__actions">
          <button
            class="secondary-button"
            type="button"
            :disabled="listLoading || pagination.page <= 1"
            @click="handlePageChange(pagination.page - 1)"
          >
            上一页
          </button>
          <button
            v-for="page in visiblePages"
            :key="page"
            :class="['pagination-page', { 'pagination-page--active': page === pagination.page }]"
            type="button"
            :disabled="listLoading || page === pagination.page"
            @click="handlePageChange(page)"
          >
            {{ page }}
          </button>
          <button
            class="secondary-button"
            type="button"
            :disabled="listLoading || pagination.page >= pageCount || pagination.total === 0"
            @click="handlePageChange(pagination.page + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAlertList } from '../api/alert'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingBlock from '../components/common/LoadingBlock.vue'
import PageHeader from '../components/common/PageHeader.vue'
import {
  displayText,
  formatAlertLevel,
  formatAlertStatus,
  formatDateTime,
  formatHealthScore,
  formatPercent
} from '../utils/formatters'

const route = useRoute()
const router = useRouter()

const DEFAULT_PAGE_SIZE = 10
const DEFAULT_FILTERS = {
  deviceId: '',
  alertLevel: '',
  alertStatus: ''
}

const levelOptions = ['low', 'medium', 'high'].map((value) => ({
  value,
  label: formatAlertLevel(value)
}))
const statusOptions = ['unhandled', 'processing', 'resolved'].map((value) => ({
  value,
  label: formatAlertStatus(value)
}))

const filters = reactive({
  ...DEFAULT_FILTERS,
  deviceId: normalizeQueryValue(route.query.device_code || route.query.device_id)
})
const pagination = reactive({
  page: 1,
  size: DEFAULT_PAGE_SIZE,
  total: 0
})

const alertItems = ref([])
const listLoading = ref(false)
const listError = ref('')
const hasLoaded = ref(false)
let listRequestId = 0

const hasActiveFilters = computed(() =>
  Boolean(filters.deviceId.trim() || filters.alertLevel || filters.alertStatus)
)
const pageCount = computed(() => Math.max(1, Math.ceil(pagination.total / pagination.size) || 1))
const emptyTitle = computed(() =>
  hasActiveFilters.value ? '当前筛选条件下暂无匹配告警' : '当前暂无告警记录'
)
const headerMetaText = computed(() => {
  if (listLoading.value) {
    return '正在同步告警列表。'
  }

  if (listError.value) {
    return '告警列表请求失败，请稍后重试。'
  }

  if (!hasLoaded.value) {
    return '进入页面后自动查询告警列表。'
  }

  return `当前页 ${alertItems.value.length} 条，列表总计 ${pagination.total} 条。`
})
const rangeText = computed(() => {
  if (!pagination.total) {
    return `当前每页 ${pagination.size} 条，共 0 条记录`
  }

  const start = (pagination.page - 1) * pagination.size + 1
  const end = Math.min(pagination.total, start + alertItems.value.length - 1)
  return `当前显示 ${start}-${end} 条，共 ${pagination.total} 条记录`
})
const visiblePages = computed(() => {
  const total = pageCount.value
  const current = pagination.page
  const start = Math.max(1, current - 2)
  const end = Math.min(total, start + 4)
  return Array.from({ length: end - start + 1 }, (_, index) => start + index)
})
const alertSummaryCards = computed(() => {
  const unhandledCount = countAlertsByStatus(['unhandled'])
  const processingCount = countAlertsByStatus(['processing'])
  const resolvedCount = countAlertsByStatus(['resolved'])
  const highRiskCount = alertItems.value.filter((item) => getRiskTone(item.alert_level) === 'danger').length

  return [
    {
      key: 'unhandled',
      label: '当前页未处理',
      value: unhandledCount,
      description: '待运维复核',
      icon: '!',
      tone: unhandledCount > 0 ? 'danger' : 'muted'
    },
    {
      key: 'processing',
      label: '当前页处理中',
      value: processingCount,
      description: '处置跟进中',
      icon: '~',
      tone: processingCount > 0 ? 'warning' : 'muted'
    },
    {
      key: 'resolved',
      label: '当前页已处理',
      value: resolvedCount,
      description: '闭环完成',
      icon: '✓',
      tone: 'success'
    },
    {
      key: 'high-risk',
      label: '当前页高风险',
      value: highRiskCount,
      description: '优先关注',
      icon: '▲',
      tone: highRiskCount > 0 ? 'danger' : 'muted'
    },
    {
      key: 'page-total',
      label: '当前页告警数',
      value: alertItems.value.length,
      description: `每页 ${pagination.size} 条`,
      icon: '#',
      tone: 'primary'
    }
  ]
})

onMounted(() => {
  fetchAlerts()
})

async function fetchAlerts() {
  const requestId = ++listRequestId
  listLoading.value = true
  listError.value = ''

  try {
    const result = await getAlertList(buildApiParams())

    if (requestId !== listRequestId) {
      return
    }

    const pageData = normalizeAlertPage(normalizePayload(result))
    alertItems.value = pageData.items
    pagination.total = pageData.total
    pagination.page = pageData.page
    pagination.size = pageData.size
    hasLoaded.value = true
  } catch (error) {
    if (requestId !== listRequestId) {
      return
    }

    alertItems.value = []
    pagination.total = 0
    hasLoaded.value = true
    listError.value = error.message || '告警列表加载失败'
  } finally {
    if (requestId === listRequestId) {
      listLoading.value = false
    }
  }
}

function handleSearch() {
  pagination.page = 1
  fetchAlerts()
}

function handleReset() {
  Object.assign(filters, DEFAULT_FILTERS)
  pagination.page = 1
  fetchAlerts()
}

function handlePageChange(nextPage) {
  if (nextPage < 1 || nextPage === pagination.page || nextPage > pageCount.value) {
    return
  }

  pagination.page = nextPage
  fetchAlerts()
}

function goDiagnosis(alert) {
  if (!alert?.alert_id) {
    return
  }

  router.push({ name: 'alert-diagnosis-detail', params: { id: alert.alert_id } })
}

function buildApiParams() {
  const params = {
    page: pagination.page,
    size: pagination.size
  }

  if (filters.deviceId.trim()) {
    params.device_id = filters.deviceId.trim()
  }

  if (filters.alertLevel) {
    params.alert_level = filters.alertLevel
  }

  if (filters.alertStatus) {
    params.alert_status = filters.alertStatus
  }

  return params
}

function normalizePayload(result) {
  if (!result || typeof result !== 'object') {
    return {}
  }

  return 'data' in result ? result.data || {} : result
}

function normalizeAlertPage(payload) {
  const source = normalizePayload(payload)
  const rawItems = Array.isArray(source.items)
    ? source.items
    : Array.isArray(source.records)
      ? source.records
      : Array.isArray(source.list)
        ? source.list
        : Array.isArray(source.rows)
          ? source.rows
          : []
  const items = rawItems.map((item) => normalizeAlertRecord(item))

  return {
    items,
    total: toNonNegativeInteger(source.total, items.length),
    page: toPositiveInteger(source.page, pagination.page),
    size: toPositiveInteger(source.size, pagination.size)
  }
}

function normalizeAlertRecord(record) {
  const source = record && typeof record === 'object' ? record : {}

  return {
    alert_id: source.alert_id ?? '',
    device_id: source.device_id ?? '',
    device_code: source.device_code ?? '',
    alert_level: source.alert_level ?? '',
    alert_status: source.alert_status ?? '',
    alert_status_text: source.alert_status_text ?? '',
    risk_score: source.risk_score ?? null,
    health_score: source.health_score ?? null,
    alert_time: source.alert_time ?? '',
    created_at: source.created_at ?? source.create_time ?? '',
    updated_at: source.updated_at ?? source.update_time ?? '',
    message: source.message ?? source.alert_message ?? '',
    alert_message: source.alert_message ?? source.message ?? ''
  }
}

function countAlertsByStatus(statusList) {
  return alertItems.value.filter((item) => statusList.includes(normalizeAlertStatusKey(item.alert_status))).length
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

function isResolved(status) {
  return normalizeAlertStatusKey(status) === 'resolved'
}

function formatRiskScore(value) {
  return formatPercent(value, 2, '--')
}

function displayValue(value) {
  return displayText(value, '--')
}

function normalizeQueryValue(value) {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0].trim() : ''
  }

  return typeof value === 'string' ? value.trim() : ''
}

function toPositiveInteger(value, fallback) {
  const parsedValue = Number.parseInt(value, 10)
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : fallback
}

function toNonNegativeInteger(value, fallback) {
  const parsedValue = Number.parseInt(value, 10)
  return Number.isFinite(parsedValue) && parsedValue >= 0 ? parsedValue : fallback
}
</script>

<style scoped>
.alert-center-page {
  width: 100%;
  max-width: var(--layout-page-max);
  margin: 0 auto;
  display: grid;
  gap: var(--space-6);
}

.alert-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-4);
}

.alert-summary-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 0;
  min-height: 128px;
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-sm);
}

.alert-summary-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  border-radius: 50%;
  font-size: 1.15rem;
  font-weight: 820;
}

.alert-summary-card__body {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.alert-summary-card span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 760;
}

.alert-summary-card strong {
  color: var(--color-text-primary);
  font-size: 2rem;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.alert-summary-card p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.alert-summary-card--danger .alert-summary-card__icon {
  color: var(--color-danger);
  background: var(--color-danger-soft);
}

.alert-summary-card--warning .alert-summary-card__icon {
  color: var(--color-warning);
  background: var(--color-warning-soft);
}

.alert-summary-card--success .alert-summary-card__icon {
  color: var(--color-success);
  background: var(--color-success-soft);
}

.alert-summary-card--primary .alert-summary-card__icon {
  color: var(--color-primary);
  background: var(--color-info-soft);
}

.alert-summary-card--muted .alert-summary-card__icon {
  color: var(--color-text-muted);
  background: var(--color-neutral-soft);
}

.alert-filter-bar,
.alert-table-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-sm);
}

.alert-filter-bar {
  display: grid;
  grid-template-columns: minmax(260px, 1.3fr) minmax(180px, 0.8fr) minmax(180px, 0.8fr) auto;
  gap: var(--space-4);
  align-items: end;
  padding: var(--space-5);
}

.filter-field {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.filter-field span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 760;
}

.filter-field input,
.filter-field select {
  width: 100%;
  min-height: 42px;
  padding: 0 var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
  color: var(--color-text-primary);
  outline: none;
}

.filter-field input:focus,
.filter-field select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  background: #fff;
}

.filter-field input:disabled {
  color: var(--color-text-muted);
  background: #f8fafc;
}

.filter-actions,
.alert-table-card__meta,
.alert-pagination,
.alert-pagination__actions,
.alert-table__action-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.filter-actions {
  justify-content: flex-end;
  white-space: nowrap;
}

.alert-table-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
}

.alert-table-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.alert-table-card__header h3 {
  margin: 4px 0 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.alert-table-card__meta {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.alert-table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.alert-table {
  width: 100%;
  min-width: 1180px;
  border-collapse: collapse;
}

.alert-table th,
.alert-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  vertical-align: middle;
  line-height: 1.5;
}

.alert-table th {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 780;
  background: var(--color-bg-panel);
  white-space: nowrap;
}

.alert-table tbody tr:last-child td {
  border-bottom: 0;
}

.alert-table__row td:first-child {
  box-shadow: inset 0 0 0 transparent;
}

.alert-table__row--danger td:first-child {
  box-shadow: inset 3px 0 0 var(--color-danger);
}

.alert-table__row--warning td:first-child {
  box-shadow: inset 3px 0 0 var(--color-warning);
}

.alert-table__row:hover {
  background: rgba(37, 99, 235, 0.035);
}

.alert-table__mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-weight: 700;
}

.alert-table__score {
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.alert-table__score--danger {
  color: var(--color-danger);
}

.alert-table__score--warning {
  color: var(--color-warning);
}

.alert-table__score--success,
.alert-table__score--health {
  color: var(--color-success);
}

.alert-table__time {
  white-space: nowrap;
}

.alert-table__message {
  max-width: 280px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-table__action-col,
.alert-table__action-cell {
  min-width: 180px;
  text-align: right;
}

.alert-table__action-cell {
  justify-content: flex-end;
}

.table-action-button {
  min-height: 32px;
  padding: 0 12px;
  white-space: nowrap;
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

.alert-pagination {
  justify-content: space-between;
  gap: var(--space-4);
}

.alert-pagination p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.alert-pagination__actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.pagination-page {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  height: 36px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--color-text-secondary);
  font-weight: 760;
  cursor: pointer;
}

.pagination-page--active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: var(--color-text-inverse);
}

.pagination-page:disabled {
  cursor: default;
}

@media (max-width: 1280px) {
  .alert-summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .alert-filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .alert-summary-grid,
  .alert-filter-bar {
    grid-template-columns: 1fr;
  }

  .alert-table-card__header,
  .alert-pagination {
    display: grid;
  }

  .filter-actions,
  .alert-pagination__actions {
    justify-content: flex-start;
  }
}
</style>
