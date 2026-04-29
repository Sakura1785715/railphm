<template>
  <section class="device-ledger-page">
    <div class="device-ledger-topbar">
      <div class="device-ledger-topbar__content">
        <p class="page-tag">设备台账</p>
        <h2>设备台账</h2>
        <p class="page-description">
          查看系统内设备基础档案信息，并支持最小范围筛选与详情跳转，作为后续监测、预测和告警业务的统一设备入口。
        </p>
      </div>

      <div class="device-ledger-topbar__meta">
        <div class="device-ledger-topbar__status">
          <span :class="['status-pill', `status-pill--${summaryTone}`]">{{ summaryLabel }}</span>
          <span class="device-ledger-topbar__summary">{{ summaryDescription }}</span>
        </div>
        <button v-if="canManageDevice" class="primary-button" type="button" @click="openCreateDeviceForm">
          新增设备
        </button>
      </div>
    </div>

    <p v-if="opsPermissionMessage" class="device-permission-message">{{ opsPermissionMessage }}</p>
    <p v-if="operationMessage" class="device-operation-message">{{ operationMessage }}</p>

    <DeviceFilterBar
      v-model:device-id="filters.deviceId"
      v-model:car-no="filters.carNo"
      v-model:device-status="filters.deviceStatus"
      :loading="loading"
      :status-options="statusOptions"
      @search="handleSearch"
      @reset="handleReset"
    />

    <DeviceTable
      :rows="devices"
      :loading="loading"
      :error="errorMessage"
      :page="pagination.page"
      :size="pagination.size"
      :total="pagination.total"
      :empty-text="emptyText"
      :detail-query="detailQuery"
      :can-edit="canManageDevice"
      @retry="fetchDevices"
      @page-change="handlePageChange"
      @edit="openEditDeviceForm"
    />

    <DeviceFormModal
      :visible="formVisible"
      :mode="formMode"
      :initial-device="editingDevice"
      :submitting="formSubmitting"
      :error-message="formError"
      @submit="handleDeviceFormSubmit"
      @close="closeDeviceForm"
    />
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DeviceFilterBar from '../components/device/DeviceFilterBar.vue'
import DeviceFormModal from '../components/device/DeviceFormModal.vue'
import DeviceTable from '../components/device/DeviceTable.vue'
import { createDevice, getDeviceList, updateDevice } from '../api/device'
import { isAdmin, isOps } from '../utils/auth'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  deviceId: '',
  carNo: '',
  deviceStatus: ''
})

const pagination = reactive({
  page: 1,
  size: 5,
  total: 0
})

const devices = ref([])
const loading = ref(false)
const errorMessage = ref('')
const formVisible = ref(false)
const formMode = ref('create')
const editingDevice = ref(null)
const formSubmitting = ref(false)
const formError = ref('')
const operationMessage = ref('')
const canManageDevice = computed(() => isAdmin())
const opsPermissionMessage = computed(() =>
  isOps() ? '当前账号为运维用户，可查看设备台账与详情；新增和编辑设备需要系统管理员权限。' : ''
)

const statusOptions = [
  {
    label: '在册运行',
    value: '1'
  },
  {
    label: '停用观察',
    value: '0'
  }
]

const hasActiveFilters = computed(
  () => Boolean(filters.deviceId.trim() || filters.carNo.trim() || filters.deviceStatus !== '')
)

const emptyText = computed(() =>
  hasActiveFilters.value ? '当前筛选条件下无匹配设备。' : '当前暂无设备台账数据。'
)

const summaryTone = computed(() => {
  if (loading.value) {
    return 'muted'
  }

  if (errorMessage.value) {
    return 'warning'
  }

  return hasActiveFilters.value ? 'default' : 'success'
})

const summaryLabel = computed(() => {
  if (loading.value) {
    return '台账加载中'
  }

  if (errorMessage.value) {
    return '台账待重试'
  }

  return hasActiveFilters.value ? '已应用筛选' : '台账接口已接入'
})

const summaryDescription = computed(() => {
  if (loading.value) {
    return '正在请求 /api/v1/devices 获取设备台账数据'
  }

  if (errorMessage.value) {
    return '设备列表请求失败，可稍后重试'
  }

  if (hasActiveFilters.value) {
    return `当前返回 ${pagination.total} 条匹配记录`
  }

  return `当前共接入 ${pagination.total} 台设备`
})

const detailQuery = computed(() => buildRouteQuery())

watch(
  () => route.query,
  async (query) => {
    syncStateFromRoute(query)
    await fetchDevices()
  },
  {
    immediate: true
  }
)

async function fetchDevices() {
  loading.value = true
  errorMessage.value = ''

  try {
    const result = await getDeviceList(buildApiParams())
    const payload = result.data || {}
    devices.value = Array.isArray(payload.items) ? payload.items : []
    pagination.total = typeof payload.total === 'number' ? payload.total : devices.value.length
    pagination.page = typeof payload.page === 'number' ? payload.page : pagination.page
    pagination.size = typeof payload.size === 'number' ? payload.size : pagination.size
  } catch (error) {
    devices.value = []
    pagination.total = 0
    errorMessage.value = error.message || '设备台账加载失败'
  } finally {
    loading.value = false
  }
}

function openCreateDeviceForm() {
  formMode.value = 'create'
  editingDevice.value = null
  formError.value = ''
  operationMessage.value = ''
  formVisible.value = true
}

function openEditDeviceForm(device) {
  formMode.value = 'edit'
  editingDevice.value = device
  formError.value = ''
  operationMessage.value = ''
  formVisible.value = true
}

function closeDeviceForm() {
  if (formSubmitting.value) {
    return
  }

  formVisible.value = false
  formMode.value = 'create'
  editingDevice.value = null
  formError.value = ''
}

async function handleDeviceFormSubmit(payload) {
  if (formSubmitting.value) {
    return
  }

  formSubmitting.value = true
  formError.value = ''

  try {
    if (formMode.value === 'edit') {
      await updateDevice(editingDevice.value.device_id, payload)
      operationMessage.value = '设备信息编辑成功，列表已刷新'
      formVisible.value = false
      await fetchDevices()
      return
    }

    const result = await createDevice(payload)
    const createdDevice = result?.data || {}
    operationMessage.value = '设备新增成功，列表已刷新'
    formVisible.value = false
    await refreshCreatedDevicePage(createdDevice)
  } catch (error) {
    formError.value = error.message || '设备信息保存失败，请稍后重试'
  } finally {
    formSubmitting.value = false
  }
}

async function refreshCreatedDevicePage(createdDevice = {}) {
  const createdDeviceId = createdDevice.device_id ? String(createdDevice.device_id) : ''

  filters.deviceId = createdDeviceId
  filters.carNo = ''
  filters.deviceStatus = ''
  pagination.page = 1

  await router.push({
    name: 'devices',
    query: createdDeviceId ? { device_id: createdDeviceId } : {}
  })
  await fetchDevices()
}

function handleSearch() {
  operationMessage.value = ''
  router.push({
    name: 'devices',
    query: buildRouteQuery({
      page: 1
    })
  })
}

function handleReset() {
  operationMessage.value = ''
  router.push({
    name: 'devices'
  })
}

function handlePageChange(nextPage) {
  if (nextPage === pagination.page || nextPage < 1) {
    return
  }

  operationMessage.value = ''
  router.push({
    name: 'devices',
    query: buildRouteQuery({
      page: nextPage
    })
  })
}

function syncStateFromRoute(query) {
  filters.deviceId = normalizeQueryValue(query.device_id)
  filters.carNo = normalizeQueryValue(query.car_no)
  filters.deviceStatus = normalizeQueryValue(query.device_status)
  pagination.page = toPositiveInteger(query.page, 1)
}

function buildApiParams() {
  const params = {
    page: pagination.page,
    size: pagination.size
  }

  if (filters.deviceId.trim()) {
    params.device_id = filters.deviceId.trim()
  }

  if (filters.carNo.trim()) {
    params.car_no = filters.carNo.trim()
  }

  if (filters.deviceStatus !== '') {
    params.device_status = filters.deviceStatus
  }

  return params
}

function buildRouteQuery(overrides = {}) {
  const query = {}
  const currentPage = overrides.page ?? pagination.page

  if (filters.deviceId.trim()) {
    query.device_id = filters.deviceId.trim()
  }

  if (filters.carNo.trim()) {
    query.car_no = filters.carNo.trim()
  }

  if (filters.deviceStatus !== '') {
    query.device_status = filters.deviceStatus
  }

  if (currentPage > 1) {
    query.page = String(currentPage)
  }

  return query
}

function normalizeQueryValue(value) {
  return typeof value === 'string' ? value : ''
}

function toPositiveInteger(value, fallback) {
  const parsedValue = Number.parseInt(value, 10)
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : fallback
}
</script>

<style scoped>
.device-ledger-page {
  display: grid;
  gap: 20px;
}

.device-ledger-topbar,
.device-ledger-topbar__meta {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.device-ledger-topbar {
  padding: 6px 4px 0;
}

.device-ledger-topbar__summary {
  max-width: 280px;
  color: #5b6d86;
  text-align: right;
  line-height: 1.6;
}

.device-ledger-topbar__status {
  display: grid;
  justify-items: end;
  gap: 8px;
}

.device-operation-message {
  margin: 0;
  padding: 12px 16px;
  color: #027a48;
  background: #ecfdf3;
  border: 1px solid #abefc6;
  border-radius: 14px;
  font-size: 0.94rem;
  font-weight: 650;
}

.device-permission-message {
  margin: 0;
  padding: 12px 16px;
  color: #915f00;
  background: #fffaeb;
  border: 1px solid #fedf89;
  border-radius: 14px;
  font-size: 0.94rem;
  font-weight: 650;
}

@media (max-width: 768px) {
  .device-ledger-topbar,
  .device-ledger-topbar__meta {
    flex-direction: column;
  }

  .device-ledger-topbar__status {
    justify-items: start;
  }

  .device-ledger-topbar__summary {
    max-width: none;
    text-align: left;
  }
}
</style>
