<template>
  <section class="alert-center-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">告警中心</p>
        <h2>设备告警中心</h2>
        <p class="page-description">
          集中展示系统生成的设备告警记录，支持按设备编号、告警等级和告警状态进行查询，并查看单条告警详情。
        </p>
      </div>

      <div class="monitor-topbar__meta">
        <span :class="['status-pill', `status-pill--${statusTone}`]">{{ statusLabel }}</span>
        <span class="monitor-topbar__summary">{{ statusDescription }}</span>
      </div>
    </div>

    <form class="device-filter-card alert-filter-card" @submit.prevent="handleSearch">
      <div class="device-filter-card__header alert-filter-card__header">
        <div>
          <p class="section-tag">条件筛选</p>
          <h3>告警查询条件</h3>
        </div>
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

    <section class="alert-content">
      <article class="device-table-card alert-list-card">
        <div class="device-table-card__header">
          <div>
            <p class="section-tag">告警列表</p>
            <h3>告警记录清单</h3>
            <p class="device-table-card__description">
              当前展示告警摘要字段，点击“查看详情”后在下方展示完整告警信息。
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

        <div v-else class="alert-table-wrapper">
          <table class="alert-table">
            <thead>
              <tr>
                <th>告警ID</th>
                <th>设备编号</th>
                <th>告警等级</th>
                <th>告警状态</th>
                <th class="alert-table__time-col">告警时间</th>
                <th>告警位置</th>
                <th class="alert-table__action-col">操作</th>
              </tr>
            </thead>

            <tbody v-if="listLoading">
              <tr>
                <td colspan="7" class="alert-table__placeholder">正在加载告警列表...</td>
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
                  <span :class="['alert-badge', getRiskLevelClass(item.alert_level)]">
                    {{ getLevelLabel(item.alert_level) }}
                  </span>
                </td>
                <td>
                  <span :class="['alert-badge', getStatusClass(item.alert_status)]">
                    {{ getStatusLabel(item.alert_status) }}
                  </span>
                </td>
                <td class="alert-table__time">{{ formatDateTimeForList(item.alert_time) }}</td>
                <td class="alert-table__position" :title="displayValue(item.alert_position)">
                  {{ displayValue(item.alert_position) }}
                </td>
                <td class="alert-table__action-cell">
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
                <td colspan="7" class="alert-table__placeholder">{{ emptyText }}</td>
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

      <article class="device-table-card alert-detail-card">
        <div class="device-table-card__header alert-detail-card__header">
          <div>
            <p class="section-tag">告警详情</p>
            <h3>告警记录详情</h3>
          </div>

          <div class="device-table-card__meta">
            <span v-if="selectedAlertId" class="device-chip">当前告警 {{ displayValue(selectedAlertId) }}</span>
            <span v-else class="status-pill status-pill--muted">未选择记录</span>
          </div>
        </div>

        <div v-if="handleSuccess" class="alert-handle-message alert-handle-message--success">
          {{ handleSuccess }}
        </div>

        <div v-if="!selectedAlertId" class="alert-detail-placeholder">
          请选择一条告警记录查看详情
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
          <div class="alert-detail-message">
            <div class="alert-detail-message__header">
              <span>告警信息</span>
              <div class="alert-detail-summary">
                <span :class="['alert-badge', getRiskLevelClass(alertDetail.alert_level)]">
                  {{ getLevelLabel(alertDetail.alert_level) }}
                </span>
                <span :class="['alert-badge', getStatusClass(alertDetail.alert_status)]">
                  {{ getStatusLabel(alertDetail.alert_status) }}
                </span>
              </div>
            </div>
            <strong>{{ displayValue(alertDetail.message) }}</strong>
          </div>

          <div class="alert-handle-panel">
            <div class="alert-handle-panel__header">
              <div>
                <p class="section-tag">告警处理</p>
                <h4>处理状态</h4>
              </div>

              <span v-if="isAlertResolved" class="status-pill status-pill--success">该告警已处理</span>
              <button
                v-else-if="canHandleAlert && !handleFormVisible"
                class="primary-button"
                type="button"
                @click="openHandleForm"
              >
                处理告警
              </button>
            </div>

            <form v-if="handleFormVisible" class="alert-handle-form" @submit.prevent="submitAlertHandle">
              <div class="alert-handle-form__grid">
                <label class="filter-field">
                  <span>处理人ID</span>
                  <input
                    v-model.trim="handleForm.handlerId"
                    type="text"
                    inputmode="numeric"
                    placeholder="请输入处理人ID"
                    :disabled="handleSubmitting"
                  />
                </label>

                <label class="filter-field alert-handle-form__note">
                  <span>处理说明</span>
                  <textarea
                    v-model="handleForm.handleNote"
                    class="alert-handle-textarea"
                    placeholder="请输入处理说明"
                    :disabled="handleSubmitting"
                  ></textarea>
                </label>
              </div>

              <div v-if="handleError" class="alert-handle-message alert-handle-message--error">
                {{ handleError }}
              </div>

              <div class="alert-handle-form__actions">
                <button class="primary-button" type="submit" :disabled="handleSubmitting">
                  {{ handleSubmitting ? '提交中...' : '提交处理' }}
                </button>
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="handleSubmitting"
                  @click="cancelHandleForm"
                >
                  取消
                </button>
              </div>
            </form>
          </div>

          <div class="alert-detail-groups">
            <div v-for="group in detailGroups" :key="group.title" class="alert-detail-section">
              <h4>{{ group.title }}</h4>
              <div class="alert-detail-grid">
                <div v-for="field in group.fields" :key="field.key" class="alert-detail-item">
                  <span>{{ field.label }}</span>
                  <strong :title="field.value">{{ field.value }}</strong>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="alert-detail-placeholder">
          当前告警暂无可展示的详情信息
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getAlertDetail, getAlertList, updateAlertStatus } from '../api/alert'
import { hasAnyRole } from '../utils/auth'

const route = useRoute()

const DEFAULT_PAGE_SIZE = 5
const DEFAULT_FILTERS = {
  deviceId: '',
  alertLevel: '',
  alertStatus: ''
}

const levelOptions = ['HIGH', 'MEDIUM', 'LOW']
const statusOptions = ['PENDING', 'PROCESSING', 'RESOLVED']

const queryDeviceId = normalizeQueryDeviceId(route.query.device_id)
const filters = reactive({
  ...DEFAULT_FILTERS,
  deviceId: queryDeviceId || DEFAULT_FILTERS.deviceId
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

const selectedAlertId = ref('')
const alertDetail = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const handleFormVisible = ref(false)
const handleSubmitting = ref(false)
const handleError = ref('')
const handleSuccess = ref('')
const handleForm = reactive({
  handlerId: '',
  handleNote: ''
})

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
    return '正在请求告警列表。'
  }

  if (listError.value) {
    return '告警列表请求失败，可调整筛选条件后重新查询。'
  }

  if (hasActiveFilters.value) {
    return `当前筛选条件下返回 ${pagination.total} 条告警记录。`
  }

  return pagination.total > 0
    ? `当前共接入 ${pagination.total} 条告警记录。`
    : '当前暂无告警记录。'
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

const isAlertResolved = computed(() =>
  String(alertDetail.value?.alert_status || '').toUpperCase() === 'RESOLVED'
)

const canHandleAlert = computed(() => {
  const status = String(alertDetail.value?.alert_status || '').toUpperCase()
  return hasAnyRole(['OPS', 'ADMIN']) && (status === 'PENDING' || status === 'PROCESSING')
})

const detailGroups = computed(() => {
  if (!alertDetail.value) {
    return []
  }

  return [
    {
      title: '基础信息',
      fields: [
        { key: 'alert_id', label: '告警ID', value: displayValue(alertDetail.value.alert_id) },
        { key: 'device_id', label: '设备编号', value: displayValue(alertDetail.value.device_id) },
        { key: 'alert_level', label: '告警等级', value: displayValue(getLevelLabel(alertDetail.value.alert_level)) },
        { key: 'alert_status', label: '告警状态', value: displayValue(getStatusLabel(alertDetail.value.alert_status)) },
        { key: 'alert_time', label: '告警时间', value: formatDateTimeForDetail(alertDetail.value.alert_time) }
      ]
    },
    {
      title: '告警对象',
      fields: [
        { key: 'alert_position', label: '告警位置', value: displayValue(alertDetail.value.alert_position) },
        { key: 'alert_source', label: '告警来源', value: displayValue(alertDetail.value.alert_source) },
        { key: 'alert_object_type', label: '对象类型', value: displayValue(alertDetail.value.alert_object_type) },
        { key: 'alert_object_code', label: '对象编号', value: displayValue(alertDetail.value.alert_object_code) }
      ]
    },
    {
      title: '关联与处理',
      fields: [
        { key: 'risk_result_id', label: '风险结果ID', value: displayValue(alertDetail.value.risk_result_id) },
        { key: 'handler_id', label: '处理人ID', value: displayValue(alertDetail.value.handler_id) },
        { key: 'handle_time', label: '处理时间', value: formatDateTimeForDetail(alertDetail.value.handle_time) },
        { key: 'handle_desc', label: '处理说明', value: displayValue(alertDetail.value.handle_desc) }
      ]
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
    const items = await enrichAlertListItems(pageData.items, requestId)

    if (requestId !== listRequestId) {
      return
    }

    alertItems.value = items
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
    if (isAlertResolved.value) {
      handleFormVisible.value = false
      handleError.value = ''
    }
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
  resetHandleState()
  fetchAlertDetail(nextAlertId)
}

function clearSelection() {
  selectedAlertId.value = ''
  alertDetail.value = null
  detailError.value = ''
  detailLoading.value = false
  detailRequestId += 1
  resetHandleState()
}

function openHandleForm() {
  handleFormVisible.value = true
  handleError.value = ''
  handleSuccess.value = ''
  handleForm.handlerId = alertDetail.value?.handler_id ? String(alertDetail.value.handler_id) : ''
  handleForm.handleNote = ''
}

function cancelHandleForm() {
  handleFormVisible.value = false
  handleError.value = ''
}

async function submitAlertHandle() {
  if (handleSubmitting.value || !alertDetail.value || !selectedAlertId.value) {
    return
  }

  handleError.value = ''
  handleSuccess.value = ''

  const validationMessage = validateHandleForm()
  if (validationMessage) {
    handleError.value = validationMessage
    return
  }

  const currentAlertId = selectedAlertId.value
  handleSubmitting.value = true

  try {
    const result = await updateAlertStatus(currentAlertId, {
      alert_status: 'RESOLVED',
      handler_id: Number(handleForm.handlerId),
      handle_note: handleForm.handleNote.trim()
    })

    alertDetail.value = normalizeAlertDetail(result)
    handleFormVisible.value = false
    handleSuccess.value = '告警处理成功'

    await fetchAlerts()
    handleSuccess.value = '告警处理成功'

    if (isSameAlert(selectedAlertId.value, currentAlertId)) {
      await fetchAlertDetail(currentAlertId)
    }
  } catch (error) {
    handleError.value = error.message || '告警处理失败，请稍后重试'
  } finally {
    handleSubmitting.value = false
  }
}

function validateHandleForm() {
  const handlerIdText = String(handleForm.handlerId || '').trim()
  const handleNoteText = String(handleForm.handleNote || '').trim()
  const handlerId = Number(handlerIdText)

  if (!handlerIdText) {
    return '处理人ID不能为空'
  }

  if (!Number.isInteger(handlerId) || handlerId <= 0) {
    return '处理人ID必须为正整数'
  }

  if (!handleNoteText) {
    return '处理说明不能为空'
  }

  return ''
}

function resetHandleState() {
  handleFormVisible.value = false
  handleSubmitting.value = false
  handleError.value = ''
  handleSuccess.value = ''
  handleForm.handlerId = ''
  handleForm.handleNote = ''
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
    alert_id: source.alert_id ?? '',
    device_id: source.device_id ?? '',
    alert_level: source.alert_level ?? '',
    alert_status: source.alert_status ?? '',
    alert_time: source.alert_time ?? '',
    alert_position: source.alert_position ?? '',
    alert_source: source.alert_source ?? '',
    message: source.message ?? '',
    alert_object_type: source.alert_object_type ?? '',
    alert_object_code: source.alert_object_code ?? '',
    risk_result_id: source.risk_result_id ?? '',
    handler_id: source.handler_id ?? '',
    handle_time: source.handle_time ?? '',
    handle_desc: source.handle_desc ?? ''
  }
}

function normalizeAlertDetail(result) {
  return normalizeAlertRecord(normalizePayload(result))
}

async function enrichAlertListItems(items, requestId) {
  if (!items.length || items.every((item) => displayValue(item.alert_position) !== '-')) {
    return items
  }

  const settledDetails = await Promise.allSettled(
    items.map((item) => (item.alert_id ? getAlertDetail(item.alert_id) : Promise.resolve(null)))
  )

  if (requestId !== listRequestId) {
    return items
  }

  return items.map((item, index) => {
    const settledDetail = settledDetails[index]

    if (settledDetail.status !== 'fulfilled' || !settledDetail.value) {
      return item
    }

    const detail = normalizeAlertDetail(settledDetail.value)

    return {
      ...item,
      alert_position: detail.alert_position || item.alert_position,
      alert_source: detail.alert_source || item.alert_source,
      alert_object_type: detail.alert_object_type || item.alert_object_type,
      alert_object_code: detail.alert_object_code || item.alert_object_code,
      risk_result_id: detail.risk_result_id || item.risk_result_id,
      handler_id: detail.handler_id || item.handler_id,
      handle_time: detail.handle_time || item.handle_time,
      handle_desc: detail.handle_desc || item.handle_desc
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

function formatDateTimeForList(value) {
  const displayText = displayValue(value)

  if (displayText === '-') {
    return displayText
  }

  return displayText.replace('T', ' ').slice(0, 16)
}

function formatDateTimeForDetail(value) {
  return displayValue(value).replace('T', ' ')
}

function getLevelLabel(level) {
  const normalizedLevel = String(level || '').toUpperCase()
  return normalizedLevel || '-'
}

function getStatusLabel(status) {
  const normalizedStatus = String(status || '').toUpperCase()
  return normalizedStatus || '-'
}

function getRiskLevelClass(level) {
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

function normalizeQueryDeviceId(value) {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0].trim() : ''
  }

  return typeof value === 'string' ? value.trim() : ''
}
</script>

<style scoped>
.alert-center-page {
  display: grid;
  gap: 18px;
}

.monitor-topbar,
.monitor-topbar__meta,
.alert-pagination,
.alert-detail-card__header {
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

.alert-filter-card {
  padding-bottom: 18px;
}

.alert-filter-card__header {
  margin-bottom: 14px;
}

.alert-filter-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) minmax(180px, 0.7fr) minmax(180px, 0.7fr) auto;
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

.filter-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
  white-space: nowrap;
}

.alert-content {
  display: grid;
  gap: 18px;
}

.alert-list-card,
.alert-detail-card {
  min-width: 0;
}

.alert-state,
.alert-detail-state {
  margin: 0;
}

.alert-table-wrapper {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #deebf3;
  border-radius: 14px;
}

.alert-table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
  table-layout: fixed;
}

.alert-table th,
.alert-table td {
  padding: 14px 18px;
  border-bottom: 1px solid #e6eef5;
  text-align: left;
  vertical-align: middle;
  line-height: 1.45;
}

/* 关键修复1：给表格左右两端留出更明显的呼吸空间 */
.alert-table th:first-child,
.alert-table td:first-child {
  padding-left: 24px;
}

.alert-table th:last-child,
.alert-table td:last-child {
  padding-right: 26px;
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
  background: rgba(15, 108, 133, 0.09);
  box-shadow: inset 4px 0 0 #0f6c85;
}

.alert-table th:nth-child(1),
.alert-table td:nth-child(1) {
  width: 110px;
}

.alert-table th:nth-child(2),
.alert-table td:nth-child(2) {
  width: 120px;
}

.alert-table th:nth-child(3),
.alert-table td:nth-child(3),
.alert-table th:nth-child(4),
.alert-table td:nth-child(4) {
  width: 140px;
}

.alert-table__time-col,
.alert-table__time {
  width: 180px;
  white-space: nowrap;
}

.alert-table__position {
  width: auto;
  min-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-table__action-col,
.alert-table__action-cell {
  width: 132px;
  white-space: nowrap;
  text-align: right;
}

.alert-table__mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-weight: 700;
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

.alert-detail-card {
  scroll-margin-top: 20px;
}

.alert-detail-placeholder {
  padding: 18px 22px;
  color: #5b6d86;
  background: #f8fbfd;
  border: 1px dashed #cfe0eb;
  border-radius: 14px;
}

/* 关键修复2：详情区整体左右留白更舒展 */
.alert-detail-content {
  display: grid;
  gap: 18px;
  padding-right: 2px;
}

.alert-detail-message {
  display: grid;
  gap: 12px;
  padding: 20px 24px;
  background: #f8fbfd;
  border: 1px solid #deebf3;
  border-radius: 14px;
}

.alert-detail-message__header,
.alert-detail-summary {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alert-detail-message__header {
  justify-content: space-between;
}

.alert-detail-message span,
.alert-detail-section h4 {
  margin: 0;
  color: #45617f;
  font-size: 0.9rem;
  font-weight: 760;
}

.alert-detail-message strong {
  color: #17253a;
  line-height: 1.65;
  word-break: break-word;
}

.alert-handle-panel {
  display: grid;
  gap: 14px;
  padding: 18px 20px;
  background: #fbfdff;
  border: 1px solid #deebf3;
  border-radius: 14px;
}

.alert-handle-panel__header,
.alert-handle-form__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.alert-handle-panel__header h4 {
  margin: 6px 0 0;
  color: #17253a;
  font-size: 1rem;
}

.alert-handle-form {
  display: grid;
  gap: 14px;
}

.alert-handle-form__grid {
  display: grid;
  grid-template-columns: minmax(180px, 0.45fr) minmax(280px, 1fr);
  gap: 16px;
  align-items: start;
}

.alert-handle-form__note {
  min-width: 0;
}

.alert-handle-textarea {
  width: 100%;
  min-height: 90px;
  padding: 12px 14px;
  border: 1px solid #cfe0eb;
  border-radius: 12px;
  background: #f8fbfd;
  color: #17253a;
  line-height: 1.55;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.alert-handle-textarea:focus {
  border-color: #0f6c85;
  box-shadow: 0 0 0 4px rgba(15, 108, 133, 0.12);
  background: #ffffff;
}

.alert-handle-form__actions {
  justify-content: flex-end;
}

.alert-handle-message {
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 0.92rem;
  font-weight: 650;
  line-height: 1.5;
}

.alert-handle-message--error {
  color: #b42318;
  background: #fef3f2;
  border: 1px solid #fecdca;
}

.alert-handle-message--success {
  color: #027a48;
  background: #ecfdf3;
  border: 1px solid #abefc6;
}

.alert-detail-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.alert-detail-section {
  display: grid;
  gap: 10px;
}

.alert-detail-grid {
  display: grid;
  gap: 10px;
}

/* 关键修复3：详情项内部右侧不要贴边 */
.alert-detail-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  min-height: 0;
  padding: 14px 20px 14px 16px;
  background: #f8fbfd;
  border: 1px solid #deebf3;
  border-radius: 10px;
}

.alert-detail-item span {
  flex: 0 0 88px;
  color: #5b6d86;
  font-size: 0.88rem;
  font-weight: 600;
}

.alert-detail-item strong {
  min-width: 0;
  color: #17253a;
  text-align: right;
  line-height: 1.5;
  word-break: break-word;
  padding-right: 4px;
}

/* 关键修复4：中等屏幕下减少拥挤 */
@media (max-width: 1280px) {
  .alert-detail-groups {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .alert-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .filter-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }

  .alert-detail-groups {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .monitor-topbar,
  .monitor-topbar__meta,
  .alert-pagination,
  .alert-detail-card__header,
  .alert-detail-message__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .monitor-topbar__summary {
    max-width: none;
    text-align: left;
  }

  .alert-filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    justify-content: flex-start;
  }

  .alert-table {
    min-width: 820px;
  }

  .alert-detail-item {
    display: grid;
    padding: 14px 18px;
  }

  .alert-handle-panel__header,
  .alert-handle-form__actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .alert-handle-form__grid {
    grid-template-columns: 1fr;
  }

  .alert-detail-item span {
    flex-basis: auto;
  }

  .alert-detail-item strong {
    text-align: left;
    padding-right: 0;
  }
}/* 修复：告警列表卡片头部内容贴边问题 */
.alert-list-card.device-table-card > .device-table-card__header {
  padding: 24px 24px 18px;
  box-sizing: border-box;
}

/* 修复：告警列表标题与说明文字的层级和间距 */
.alert-list-card .device-table-card__header h3 {
  margin-top: 8px;
  margin-bottom: 10px;
}

.alert-list-card .device-table-card__description {
  margin: 0;
  max-width: 680px;
  line-height: 1.7;
}

/* 修复：右侧统计信息不要贴边 */
.alert-list-card .device-table-card__meta {
  padding-top: 4px;
  padding-right: 2px;
  flex-shrink: 0;
}
/* 统一修复：筛选卡片、告警列表卡片、告警详情卡片内部内容贴边问题 */

/* 条件筛选卡片头部：条件筛选 / 告警查询条件 */
.alert-filter-card.device-filter-card > .device-filter-card__header {
  padding: 24px 32px 14px;
  box-sizing: border-box;
}

/* 条件筛选卡片表单区：设备编号 / 告警等级 / 告警状态 / 查询按钮 */
.alert-filter-card .alert-filter-grid {
  padding: 0 32px 24px;
  box-sizing: border-box;
}

/* 告警列表卡片头部：告警列表 / 告警记录清单 / 统计信息 */
.alert-list-card.device-table-card > .device-table-card__header {
  padding: 24px 32px 18px;
  box-sizing: border-box;
}

/* 告警列表底部分页区域也同步留白 */
.alert-list-card .alert-pagination {
  padding: 18px 32px 22px;
  box-sizing: border-box;
}

/* 告警详情卡片头部：告警详情 / 告警记录详情 */
.alert-detail-card.device-table-card > .device-table-card__header {
  padding: 24px 32px 18px;
  box-sizing: border-box;
}

/* 告警详情内容区：未选择提示、告警信息、基础信息等 */
.alert-detail-card > .alert-detail-placeholder,
.alert-detail-card > .alert-detail-content,
.alert-detail-card > .alert-handle-message,
.alert-detail-card > .alert-detail-state {
  margin-left: 32px;
  margin-right: 32px;
}

/* 告警详情卡片底部留白，避免内容贴住卡片底边 */
.alert-detail-card {
  padding-bottom: 24px;
}

/* 标题间距统一优化 */
.alert-filter-card .device-filter-card__header h3,
.alert-list-card .device-table-card__header h3,
.alert-detail-card .device-table-card__header h3 {
  margin-top: 8px;
  margin-bottom: 8px;
}

/* 说明文字统一不要贴边、不要过长 */
.alert-list-card .device-table-card__description {
  margin: 0;
  max-width: 720px;
  line-height: 1.7;
}

/* 右侧统计信息不要贴边 */
.alert-list-card .device-table-card__meta,
.alert-detail-card .device-table-card__meta {
  padding-top: 4px;
  flex-shrink: 0;
}

/* 小屏幕下适当收窄左右留白 */
@media (max-width: 768px) {
  .alert-filter-card.device-filter-card > .device-filter-card__header,
  .alert-list-card.device-table-card > .device-table-card__header,
  .alert-detail-card.device-table-card > .device-table-card__header {
    padding: 20px 22px 14px;
  }

  .alert-filter-card .alert-filter-grid {
    padding: 0 22px 20px;
  }

  .alert-list-card .alert-pagination {
    padding: 16px 22px 20px;
  }

  .alert-detail-card > .alert-detail-placeholder,
  .alert-detail-card > .alert-detail-content,
  .alert-detail-card > .alert-handle-message,
  .alert-detail-card > .alert-detail-state {
    margin-left: 22px;
    margin-right: 22px;
  }
}
</style>
