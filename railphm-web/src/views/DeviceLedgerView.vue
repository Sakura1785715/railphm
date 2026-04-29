<template>
  <section class="device-ledger-page">
    <PageHeader
      eyebrow="设备台账"
      title="设备台账"
      description="维护 ATP 设备基础信息，支持设备查询、详情查看和后台管理操作。"
      :meta="summaryDescription"
    >
      <template #actions>
        <StatusTag :label="summaryLabel" :type="summaryTone" />
        <button
          v-if="canManageDevice"
          class="primary-button"
          type="button"
          :disabled="loading"
          @click="openCreateDeviceForm"
        >
          新增设备
        </button>
      </template>
    </PageHeader>

    <p v-if="rolePermissionMessage" class="device-permission-message">{{ rolePermissionMessage }}</p>
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
      @size-change="handleSizeChange"
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
import PageHeader from '../components/common/PageHeader.vue'
import StatusTag from '../components/common/StatusTag.vue'
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
  size: 10,
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
const rolePermissionMessage = computed(() =>
  isOps() ? '当前账号为运维用户，可查看设备台账与详情；新增和编辑设备需要系统管理员权限。' : ''
)

const statusOptions = [
  {
    label: '正常 / 在册运行',
    value: '1'
  },
  {
    label: '停用 / 停用观察',
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
    return 'danger'
  }

  return hasActiveFilters.value ? 'info' : 'success'
})

const summaryLabel = computed(() => {
  if (loading.value) {
    return '加载中'
  }

  if (errorMessage.value) {
    return '加载失败'
  }

  return hasActiveFilters.value ? '已筛选' : '接口正常'
})

const summaryDescription = computed(() => {
  if (loading.value) {
    return '正在获取设备台账数据'
  }

  if (errorMessage.value) {
    return '设备列表请求失败，可重试或检查后端服务状态'
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
    errorMessage.value = getErrorMessage(error, '设备台账加载失败')
  } finally {
    loading.value = false
  }
}

function openCreateDeviceForm() {
  if (!canManageDevice.value) {
    operationMessage.value = ''
    formError.value = '当前角色无设备维护权限'
    return
  }

  formMode.value = 'create'
  editingDevice.value = null
  formError.value = ''
  operationMessage.value = ''
  formVisible.value = true
}

function openEditDeviceForm(device) {
  if (!canManageDevice.value) {
    operationMessage.value = ''
    formError.value = '当前角色无设备维护权限'
    return
  }

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
      if (!editingDevice.value?.device_id) {
        throw new Error('未找到要编辑的设备，请刷新列表后重试')
      }

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
    formError.value = getErrorMessage(error, '设备信息保存失败，请稍后重试')

    if (isNotFoundError(error)) {
      await fetchDevices()
    }
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

async function handleSearch() {
  operationMessage.value = ''
  const nextQuery = buildRouteQuery({
    page: 1
  })

  if (isSameRouteQuery(nextQuery)) {
    pagination.page = 1
    await fetchDevices()
    return
  }

  router.push({
    name: 'devices',
    query: nextQuery
  })
}

async function handleReset() {
  operationMessage.value = ''
  filters.deviceId = ''
  filters.carNo = ''
  filters.deviceStatus = ''
  pagination.page = 1

  const resetQuery = pagination.size !== 10 ? { size: String(pagination.size) } : {}
  const targetRoute = {
    name: 'devices'
  }

  if (Object.keys(resetQuery).length) {
    targetRoute.query = resetQuery
  }

  if (isSameRouteQuery(resetQuery)) {
    await fetchDevices()
    return
  }

  router.push(targetRoute)
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

function handleSizeChange(nextSize) {
  const normalizedSize = toPositiveInteger(nextSize, pagination.size)

  if (normalizedSize === pagination.size) {
    return
  }

  operationMessage.value = ''
  router.push({
    name: 'devices',
    query: buildRouteQuery({
      page: 1,
      size: normalizedSize
    })
  })
}

function syncStateFromRoute(query) {
  filters.deviceId = normalizeQueryValue(query.device_id)
  filters.carNo = normalizeQueryValue(query.car_no)
  filters.deviceStatus = normalizeDeviceStatusQuery(query.device_status)
  pagination.page = toPositiveInteger(query.page, 1)
  pagination.size = toPositiveInteger(query.size, 10)
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
    params.device_status = Number(filters.deviceStatus)
  }

  return params
}

function buildRouteQuery(overrides = {}) {
  const query = {}
  const currentPage = overrides.page ?? pagination.page
  const currentSize = overrides.size ?? pagination.size

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

  if (currentSize !== 10) {
    query.size = String(currentSize)
  }

  return query
}

function normalizeQueryValue(value) {
  return typeof value === 'string' ? value : ''
}

function normalizeDeviceStatusQuery(value) {
  const normalizedValue = normalizeQueryValue(value)
  return normalizedValue === '0' || normalizedValue === '1' ? normalizedValue : ''
}

function toPositiveInteger(value, fallback) {
  const parsedValue = Number.parseInt(value, 10)
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : fallback
}

function isSameRouteQuery(nextQuery) {
  const currentKeys = Object.keys(route.query).sort()
  const nextKeys = Object.keys(nextQuery).sort()

  if (currentKeys.length !== nextKeys.length) {
    return false
  }

  return currentKeys.every((key, index) => key === nextKeys[index] && String(route.query[key]) === String(nextQuery[key]))
}

function getErrorMessage(error, fallback) {
  if (error?.response?.status === 403 || error?.payload?.code === 403) {
    return error.message || '权限不足'
  }

  return error?.message || fallback
}

function isNotFoundError(error) {
  return error?.response?.status === 404 || error?.payload?.code === 404
}
</script>

<style scoped>
.device-ledger-page {
  display: grid;
  gap: 20px;
}

.device-operation-message {
  margin: 0;
  padding: 12px 16px;
  color: var(--color-success);
  background: var(--color-success-soft);
  border: 1px solid var(--color-success-border);
  border-radius: 14px;
  font-size: 0.94rem;
  font-weight: 650;
}

.device-permission-message {
  margin: 0;
  padding: 12px 16px;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border: 1px solid var(--color-warning-border);
  border-radius: 14px;
  font-size: 0.94rem;
  font-weight: 650;
}
</style>
