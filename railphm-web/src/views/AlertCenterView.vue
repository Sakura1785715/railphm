<template>
  <section class="alert-center-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">告警中心</p>
        <h2>设备告警中心</h2>
        <p class="page-description">
          集中展示系统生成的设备告警记录，支持按告警等级、告警状态和设备编号进行筛选，并查看告警详情。
        </p>
      </div>

      <div class="monitor-topbar__meta">
        <span :class="['status-pill', `status-pill--${statusTone}`]">{{ statusLabel }}</span>
        <span class="monitor-topbar__summary">{{ statusDescription }}</span>
      </div>
    </div>

    <form class="device-filter-card alert-filter-card" @submit.prevent="handleSearch">
      <div class="device-filter-card__header">
        <div>
          <p class="section-tag">条件筛选</p>
          <h3>告警查询条件</h3>
        </div>
        <p class="device-filter-card__hint">当前直接使用后端告警接口进行分页与筛选，不扩展处理流转操作。</p>
      </div>

      <div class="alert-filter-grid">
        <label class="filter-field">
          <span>设备编号</span>
          <input
            v-model.trim="filters.deviceId"
            type="search"
            inputmode="numeric"
            placeholder="请输入设备编号"
            :disabled="listLoading"
          />
        </label>

        <label class="filter-field">
          <span>告警等级</span>
          <select v-model="filters.alertLevel" :disabled="listLoading">
            <option value="">全部</option>
            <option v-for="option in levelOptions" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
        </label>

        <label class="filter-field">
          <span>告警状态</span>
          <select v-model="filters.alertStatus" :disabled="listLoading">
            <option value="">全部</option>
            <option v-for="option in statusOptions" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
        </label>

        <div class="filter-actions">
          <button class="primary-button" type="submit" :disabled="listLoading">
            {{ listLoading ? '查询中...' : '查询' }}
          </button>
          <button class="secondary-button" type="button" :disabled="listLoading" @click="handleReset">
            重置
          </button>
        </div>
      </div>
    </form>

    <section class="alert-layout">
      <article class="device-table-card alert-list-card">
        <div class="device-table-card__header">
          <div>
            <p class="section-tag">告警列表</p>
            <h3>告警记录清单</h3>
            <p class="device-table-card__description">
              当前展示告警摘要字段，支持按页查看并选中单条记录获取右侧详情。
            </p>
          </div>

          <div class="device-table-card__meta">
            <span class="status-pill status-pill--default">共 {{ pagination.total }} 条告警</span>
            <span class="device-table-card__page">第 {{ pagination.page }} / {{ pageCount }} 页</span>
          </div>
        </div>

        <div v-if="listError" class="state-panel error-state alert-state">
          <h3>告警列表加载失败</h3>
          <p>{{ listError }}</p>
          <button class="secondary-button" type="button" @click="fetchAlerts">重新加载</button>
        </div>

        <div v-else class="alert-table-shell">
          <table class="alert-table">
            <thead>
              <tr>
                <th>告警ID</th>
                <th>设备编号</th>
                <th>告警等级</th>
                <th>告警状态</th>
                <th>告警时间</th>
                <th>告警位置</th>
                <th>告警来源</th>
                <th>告警信息</th>
                <th>操作</th>
              </tr>
            </thead>

            <tbody v-if="listLoading">
              <tr>
                <td colspan="9" class="alert-table__placeholder">正在加载告警列表...</td>
              </tr>
            </tbody>

            <tbody v-else-if="alertItems.length">
              <tr
                v-for="item in alertItems"
                :key="item.alert_id"
                :class="{ 'alert-table__row--active': isSelected(item.alert_id) }"
                tabindex="0"
                @click="handleSelectAlert(item)"
                @keydown.enter.prevent="handleSelectAlert(item)"
                @keydown.space.prevent="handleSelectAlert(item)"
              >
                <td class="alert-table__mono">{{ displayValue(item.alert_id) }}</td>
                <td>{{ displayValue(item.device_id) }}</td>
                <td>
                  <span :class="['alert-badge', getLevelClass(item.alert_level)]">
                    {{ getLevelLabel(item.alert_level) }}
                  </span>
                </td>
                <td>
                  <span :class="['alert-badge', getStatusClass(item.alert_status)]">
                    {{ getStatusLabel(item.alert_status) }}
                  </span>
                </td>
                <td>{{ displayValue(item.alert_time) }}</td>
                <td>{{ displayValue(item.alert_position) }}</td>
                <td>{{ displayValue(item.alert_source) }}</td>
                <td class="alert-table__message" :title="displayValue(item.message)">
                  {{ displayValue(item.message) }}
                </td>
                <td>
                  <button
                    class="secondary-button alert-table__action"
                    type="button"
                    @click.stop="handleSelectAlert(item)"
                  >
                    查看详情
                  </button>
                </td>
              </tr>
            </tbody>

            <tbody v-else>
              <tr>
                <td colspan="9" class="alert-table__placeholder">{{ emptyText }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="device-table-footer alert-pagination">
          <p class="device-table-footer__summary">{{ rangeText }}</p>
          <div class="device-table-footer__actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="listLoading || pagination.page <= 1"
              @click="handlePageChange(pagination.page - 1)"
            >
              上一页
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
        </div>
      </article>

      <aside class="device-table-card alert-detail-card">
        <div class="device-table-card__header alert-detail-card__header">
          <div>
            <p class="section-tag">告警详情</p>
            <h3>记录详情面板</h3>
            <p class="device-table-card__description">
              选中左侧记录后调用详情接口，展示告警对象、风险关联与处理信息等字段。
            </p>
          </div>

          <div class="device-table-card__meta">
            <span v-if="selectedAlertId" class="device-chip">当前告警 {{ displayValue(selectedAlertId) }}</span>
            <span v-else class="status-pill status-pill--muted">未选择记录</span>
          </div>
        </div>

        <div v-if="!selectedAlertId" class="state-panel empty-state alert-detail-state">
          请选择左侧告警记录查看详情。
        </div>

        <div v-else-if="detailLoading" class="state-panel loading-state alert-detail-state">
          正在加载告警详情...
        </div>

        <div v-else-if="detailError" class="state-panel error-state alert-detail-state">
          <h3>告警详情加载失败</h3>
          <p>{{ detailError }}</p>
          <button
            class="secondary-button"
            type="button"
            @click="fetchAlertDetail(selectedAlertId)"
          >
            重新加载详情
          </button>
        </div>

        <div v-else-if="alertDetail" class="alert-detail-content">
          <div class="alert-detail-summary">
            <span :class="['alert-badge', getLevelClass(alertDetail.alert_level)]">
              {{ getLevelLabel(alertDetail.alert_level) }}
            </span>
            <span :class="['alert-badge', getStatusClass(alertDetail.alert_status)]">
              {{ getStatusLabel(alertDetail.alert_status) }}
            </span>
          </div>

          <div class="alert-detail-grid">
            <div v-for="field in detailFields" :key="field.key" class="alert-detail-item">
              <span>{{ field.label }}</span>
              <strong :title="field.value">{{ field.value }}</strong>
            </div>
          </div>
        </div>

        <div v-else class="state-panel empty-state alert-detail-state">
          当前告警暂无可展示的详情信息。
        </div>
      </aside>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getAlertDetail, getAlertList } from '../api/alert'

const DEFAULT_PAGE_SIZE = 5
const DEFAULT_FILTERS = {
  deviceId: '',
  alertLevel: '',
  alertStatus: ''
}

const levelOptions = ['HIGH', 'MEDIUM', 'LOW']
const statusOptions = ['PENDING', 'PROCESSING', 'RESOLVED']

const filters = reactive({ ...DEFAULT_FILTERS })
const pagination = reactive({
  page: 1,
  size: DEFAULT_PAGE_SIZE,
  total: 0
})

const alertItems = ref([])
const listLoading = ref(false)
const listError = ref('')
const hasLoaded = ref(false)

const selectedAlertId = ref('')
const alertDetail = ref(null)
const detailLoading = ref(false)
const detailError = ref('')

let listRequestId = 0
let detailRequestId = 0

const hasActiveFilters = computed(
  () => Boolean(filters.deviceId.trim() || filters.alertLevel || filters.alertStatus)
)

const statusTone = computed(() => {
  if (listLoading.value) {
    return 'muted'
  }

  if (listError.value) {
    return 'warning'
  }

  if (hasActiveFilters.value) {
    return 'default'
  }

  if (hasLoaded.value) {
    return alertItems.value.length > 0 ? 'success' : 'muted'
  }

  return 'default'
})

const statusLabel = computed(() => {
  if (!hasLoaded.value && !listLoading.value) {
    return '等待查询'
  }

  if (listLoading.value) {
    return '告警加载中'
  }

  if (listError.value) {
    return '查询待处理'
  }

  if (hasActiveFilters.value) {
    return '已应用筛选'
  }

  if (hasLoaded.value) {
    return '告警数据已接入'
  }

  return '等待查询'
})

const statusDescription = computed(() => {
  if (!hasLoaded.value && !listLoading.value) {
    return '首次进入页面后将自动查询告警列表。'
  }

  if (listLoading.value) {
    return '正在请求 /api/v1/alerts 获取告警记录。'
  }

  if (listError.value) {
    return '告警列表请求失败，可调整筛选条件后重新查询。'
  }

  if (hasActiveFilters.value) {
    return `当前筛选条件下返回 ${pagination.total} 条告警记录。`
  }

  return pagination.total > 0
    ? `当前共接入 ${pagination.total} 条告警记录。`
    : '当前暂无告警记录，可继续尝试筛选或稍后刷新。'
})

const pageCount = computed(() => Math.max(1, Math.ceil(pagination.total / pagination.size) || 1))

const emptyText = computed(() =>
  hasActiveFilters.value ? '当前筛选条件下暂无匹配告警。' : '当前暂无告警记录。'
)

const rangeText = computed(() => {
  if (!pagination.total) {
    return `当前每页 ${pagination.size} 条，共 0 条记录`
  }

  if (!alertItems.value.length) {
    return `当前页暂无记录，共 ${pagination.total} 条记录`
  }

  const start = (pagination.page - 1) * pagination.size + 1
  const end = Math.min(pagination.total, start + alertItems.value.length - 1)

  return `当前显示 ${start}-${end} 条，共 ${pagination.total} 条记录，每页 ${pagination.size} 条`
})

const detailFields = computed(() => {
  if (!alertDetail.value) {
    return []
  }

  return [
    { key: 'alert_id', label: '告警ID', value: displayValue(alertDetail.value.alert_id) },
    { key: 'device_id', label: '设备编号', value: displayValue(alertDetail.value.device_id) },
    { key: 'alert_level', label: '告警等级', value: displayValue(getLevelLabel(alertDetail.value.alert_level)) },
    { key: 'alert_status', label: '告警状态', value: displayValue(getStatusLabel(alertDetail.value.alert_status)) },
    { key: 'alert_time', label: '告警时间', value: displayValue(alertDetail.value.alert_time) },
    { key: 'message', label: '告警信息', value: displayValue(alertDetail.value.message) },
    { key: 'alert_source', label: '告警来源', value: displayValue(alertDetail.value.alert_source) },
    { key: 'alert_position', label: '告警位置', value: displayValue(alertDetail.value.alert_position) },
    { key: 'alert_object_type', label: '告警对象类型', value: displayValue(alertDetail.value.alert_object_type) },
    { key: 'alert_object_code', label: '告警对象编号', value: displayValue(alertDetail.value.alert_object_code) },
    { key: 'risk_result_id', label: '风险结果ID', value: displayValue(alertDetail.value.risk_result_id) },
    { key: 'handler_id', label: '处理人ID', value: displayValue(alertDetail.value.handler_id) },
    { key: 'handle_time', label: '处理时间', value: displayValue(alertDetail.value.handle_time) },
    { key: 'handle_desc', label: '处理说明', value: displayValue(alertDetail.value.handle_desc) }
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

    if (!alertItems.value.length) {
      clearSelection()
      return
    }

    if (selectedAlertId.value && !alertItems.value.some((item) => isSameAlert(item.alert_id, selectedAlertId.value))) {
      clearSelection()
    }
  } catch (error) {
    if (requestId !== listRequestId) {
      return
    }

    alertItems.value = []
    pagination.total = 0
    hasLoaded.value = true
    listError.value = error.message || '告警列表加载失败'
    clearSelection()
  } finally {
    if (requestId === listRequestId) {
      listLoading.value = false
    }
  }
}

async function fetchAlertDetail(alertId) {
  if (!alertId) {
    return
  }

  const requestId = ++detailRequestId

  detailLoading.value = true
  detailError.value = ''
  alertDetail.value = null

  try {
    const result = await getAlertDetail(alertId)

    if (requestId !== detailRequestId) {
      return
    }

    alertDetail.value = normalizeAlertDetail(result)
  } catch (error) {
    if (requestId !== detailRequestId) {
      return
    }

    detailError.value = error.message || '告警详情加载失败'
    alertDetail.value = null
  } finally {
    if (requestId === detailRequestId) {
      detailLoading.value = false
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

function handleSelectAlert(alert) {
  const nextAlertId = alert?.alert_id

  if (!nextAlertId) {
    return
  }

  if (
    isSameAlert(nextAlertId, selectedAlertId.value) &&
    (detailLoading.value || (alertDetail.value && !detailError.value))
  ) {
    return
  }

  selectedAlertId.value = nextAlertId
  fetchAlertDetail(nextAlertId)
}

function clearSelection() {
  selectedAlertId.value = ''
  alertDetail.value = null
  detailError.value = ''
  detailLoading.value = false
  detailRequestId += 1
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

  if ('data' in result) {
    return result.data || {}
  }

  return result
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
    alert_id: source.alert_id ?? source.id ?? source.alertId ?? '',
    device_id: source.device_id ?? source.deviceId ?? '',
    alert_level: source.alert_level ?? source.level ?? source.severity ?? '',
    alert_status: source.alert_status ?? source.status ?? '',
    alert_time: source.alert_time ?? source.created_at ?? source.updated_at ?? source.timestamp ?? '',
    alert_position: source.alert_position ?? source.position ?? '',
    alert_source: source.alert_source ?? source.source ?? '',
    message: source.message ?? source.alert_message ?? source.content ?? '',
    alert_object_type: source.alert_object_type ?? source.object_type ?? '',
    alert_object_code: source.alert_object_code ?? source.object_code ?? '',
    risk_result_id: source.risk_result_id ?? source.risk_id ?? '',
    handler_id: source.handler_id ?? source.owner_id ?? '',
    handle_time: source.handle_time ?? source.handled_at ?? '',
    handle_desc: source.handle_desc ?? source.handle_description ?? ''
  }
}

function normalizeAlertDetail(result) {
  return normalizeAlertRecord(normalizePayload(result))
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

function getLevelLabel(level) {
  const normalizedLevel = String(level || '').toUpperCase()
  return normalizedLevel || '-'
}

function getStatusLabel(status) {
  const normalizedStatus = String(status || '').toUpperCase()
  return normalizedStatus || '-'
}

function getLevelClass(level) {
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

function getStatusClass(status) {
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

function isSelected(alertId) {
  return isSameAlert(alertId, selectedAlertId.value)
}

function isSameAlert(left, right) {
  return String(left) !== '' && String(left) === String(right)
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
  display: grid;
  gap: 20px;
}

.monitor-topbar,
.monitor-topbar__meta,
.alert-detail-card__header,
.alert-pagination {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.monitor-topbar__meta,
.alert-pagination {
  align-items: center;
}

.monitor-topbar__summary {
  max-width: 320px;
  text-align: right;
}

.alert-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 16px;
  align-items: end;
}

.filter-field {
  display: grid;
  gap: 8px;
}

.filter-field span {
  margin: 0;
  color: #45617f;
  font-size: 0.92rem;
  font-weight: 600;
}

.filter-field input,
.filter-field select {
  width: 100%;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid #cfe0eb;
  border-radius: 12px;
  background: #f8fbfd;
  color: #17253a;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.filter-field input:focus,
.filter-field select:focus {
  border-color: #0f6c85;
  box-shadow: 0 0 0 4px rgba(15, 108, 133, 0.12);
  background: #ffffff;
}

.filter-actions,
.alert-detail-summary,
.alert-detail-content {
  display: flex;
  gap: 12px;
}

.filter-actions {
  align-items: center;
  flex-wrap: wrap;
}

.alert-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.95fr);
  gap: 20px;
  align-items: start;
}

.alert-list-card,
.alert-detail-card {
  min-width: 0;
}

.alert-state,
.alert-detail-state {
  margin: 0;
}

.alert-table-shell {
  overflow-x: auto;
  border: 1px solid #deebf3;
  border-radius: 18px;
}

.alert-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
}

.alert-table th,
.alert-table td {
  padding: 15px 16px;
  border-bottom: 1px solid #e6eef5;
  text-align: left;
  vertical-align: middle;
}

.alert-table th {
  color: #45617f;
  font-size: 0.9rem;
  font-weight: 700;
  background: #f8fbfd;
  white-space: nowrap;
}

.alert-table tbody tr {
  transition: background-color 0.18s ease, box-shadow 0.18s ease;
  cursor: pointer;
}

.alert-table tbody tr:hover {
  background: rgba(15, 108, 133, 0.04);
}

.alert-table tbody tr:focus-visible {
  outline: 2px solid rgba(15, 108, 133, 0.28);
  outline-offset: -2px;
}

.alert-table__row--active {
  background: rgba(15, 108, 133, 0.08);
}

.alert-table__mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-weight: 700;
}

.alert-table__message {
  max-width: 320px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-table__placeholder {
  padding: 44px 24px;
  color: #5b6d86;
  text-align: center;
}

.alert-table__action {
  min-height: 36px;
  padding: 0 14px;
  white-space: nowrap;
}

.alert-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
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

.alert-detail-content {
  flex-direction: column;
}

.alert-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.alert-detail-item {
  display: grid;
  gap: 8px;
  min-height: 88px;
  padding: 16px;
  background: #f8fbfd;
  border: 1px solid #deebf3;
  border-radius: 16px;
}

.alert-detail-item span {
  color: #5b6d86;
  font-size: 0.88rem;
  font-weight: 600;
}

.alert-detail-item strong {
  color: #17253a;
  line-height: 1.6;
  word-break: break-word;
}

@media (max-width: 1200px) {
  .alert-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1080px) {
  .alert-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .monitor-topbar,
  .monitor-topbar__meta,
  .alert-detail-card__header,
  .alert-pagination,
  .filter-actions {
    flex-direction: column;
    align-items: flex-start;
  }

  .monitor-topbar__summary {
    max-width: none;
    text-align: left;
  }

  .alert-filter-grid,
  .alert-detail-grid {
    grid-template-columns: 1fr;
  }

  .alert-table {
    min-width: 980px;
  }
}
</style>
