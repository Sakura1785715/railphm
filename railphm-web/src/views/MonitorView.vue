<template>
  <section class="monitor-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">运行监测</p>
        <h2>设备运行监测</h2>
        <p class="page-description">
          按设备和时间范围查询 InfluxDB 时序监测数据，展示速度、里程、工况、温湿度等运行状态。
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
          <h3>查询条件</h3>
          <p>数据来源：InfluxDB 时序监测数据。</p>
        </div>
      </div>

      <div class="monitor-filter-grid">
        <label class="filter-field">
          <span>设备编号</span>
          <select v-model="filters.deviceCode" :disabled="loading">
            <option v-for="device in deviceOptions" :key="device.device_code" :value="device.device_code">
              {{ device.device_code }}{{ device.device_name ? ` - ${device.device_name}` : '' }}
            </option>
          </select>
        </label>

        <label class="filter-field">
          <span>开始时间</span>
          <input
            v-model.trim="filters.startTime"
            type="text"
            placeholder="2026-05-18 10:00:00"
            :disabled="loading"
          />
        </label>

        <label class="filter-field">
          <span>结束时间</span>
          <input
            v-model.trim="filters.endTime"
            type="text"
            placeholder="2026-05-18 10:10:00"
            :disabled="loading"
          />
        </label>

        <label class="filter-field">
          <span>工况标签</span>
          <input
            v-model.trim="filters.conditionLabel"
            type="text"
            placeholder="全部"
            :disabled="loading"
          />
        </label>
      </div>

      <div class="action-bar monitor-filter-card__actions">
        <button type="submit" class="primary-button" :disabled="loading">
          {{ loading ? '查询中...' : '查询监测数据' }}
        </button>
        <button type="button" class="secondary-button" :disabled="loading" @click="handleReset">
          重置
        </button>
      </div>
    </form>

    <div v-if="validationMessage" class="state-panel error-state">
      {{ validationMessage }}
    </div>

    <div v-if="loading" class="state-panel loading-state">正在加载运行监测数据...</div>

    <div v-if="errorMessage" class="state-panel error-state">
      运行监测数据加载失败：{{ errorMessage }}
    </div>

    <div v-if="emptyMessage" class="state-panel empty-state">
      {{ emptyMessage }}
    </div>

    <div class="monitor-overview-grid">
      <article class="monitor-overview-card">
        <span>设备编号</span>
        <strong>{{ overviewDeviceCode }}</strong>
      </article>
      <article class="monitor-overview-card">
        <span>时间范围</span>
        <strong>{{ overviewStartTime }} 至 {{ overviewEndTime }}</strong>
      </article>
      <article class="monitor-overview-card">
        <span>监测点数</span>
        <strong>{{ pointCount }}</strong>
      </article>
      <article class="monitor-overview-card">
        <span>当前工况</span>
        <strong>{{ latestConditionLabel }}</strong>
      </article>
    </div>

    <LineTrendChart
      title="速度与里程趋势"
      description="基于后端返回的 InfluxDB 时序点渲染速度和里程变化。"
      :x-axis-data="overviewXAxisData"
      :series="overviewChartSeries"
      :loading="loading"
      :empty="!hasAnyPoint"
      :error="errorMessage"
      height="360px"
    />

    <section class="monitor-section">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">环境与工况</p>
          <h3>监测明细</h3>
        </div>
        <p>展示样本时间、工况标签、站点、天气、温湿度和经纬度等辅助信息。</p>
      </div>

      <div class="monitor-table-wrapper">
        <table class="monitor-table">
          <thead>
            <tr>
              <th>采样时间</th>
              <th>原始时间</th>
              <th>速度</th>
              <th>里程</th>
              <th>工况</th>
              <th>站名</th>
              <th>温度</th>
              <th>湿度</th>
              <th>天气</th>
              <th>经纬度</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tableRows" :key="`${row.sample_time}-${row.source_unique_id || row.source_time}`">
              <td>{{ row.sample_time || '-' }}</td>
              <td>{{ row.source_time || '-' }}</td>
              <td>{{ formatNumber(row.speed) }}</td>
              <td>{{ formatNumber(row.mileage) }}</td>
              <td>{{ row.condition_label || '-' }}</td>
              <td>{{ row.station_name || '-' }}</td>
              <td>{{ formatNumber(row.outdoor_temperature) }}</td>
              <td>{{ formatNumber(row.humidity) }}</td>
              <td>{{ row.weather || '-' }}</td>
              <td>{{ formatCoordinate(row) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { LineTrendChart } from '../components/chart'
import { getDeviceList } from '../api/device'
import { getMonitorHistory } from '../api/monitor'

const route = useRoute()

const DEFAULT_FILTERS = {
  deviceCode: 'ATP001',
  startTime: '2026-05-18 10:00:00',
  endTime: '2026-05-18 10:10:00',
  conditionLabel: ''
}
const FALLBACK_DEVICES = [
  { device_code: 'ATP001', device_name: 'ATP车载设备001' },
  { device_code: 'ATP002', device_name: 'ATP车载设备002' },
  { device_code: 'ATP003', device_name: 'ATP车载设备003' }
]

const queryDeviceCode = normalizeQueryValue(route.query.device_code || route.query.device_id)
const filters = reactive({
  ...DEFAULT_FILTERS,
  deviceCode: queryDeviceCode || DEFAULT_FILTERS.deviceCode
})
const monitorData = ref(null)
const devices = ref([])
const loading = ref(false)
const errorMessage = ref('')
const validationMessage = ref('')

const deviceOptions = computed(() => (devices.value.length > 0 ? devices.value : FALLBACK_DEVICES))
const seriesRows = computed(() => {
  const rows = monitorData.value?.series
  return Array.isArray(rows) ? rows : []
})
const overviewXAxisData = computed(() => seriesRows.value.map((row) => row.sample_time).filter(Boolean))
const overviewChartSeries = computed(() => [
  {
    name: '速度',
    unit: 'km/h',
    data: seriesRows.value.map((row) => toNumberOrNull(row.speed))
  },
  {
    name: '里程',
    unit: 'm',
    data: seriesRows.value.map((row) => toNumberOrNull(row.mileage))
  }
])
const tableRows = computed(() => seriesRows.value.slice(0, 80))
const pointCount = computed(() => monitorData.value?.count ?? seriesRows.value.length)
const hasAnyPoint = computed(() => seriesRows.value.length > 0)
const emptyMessage = computed(() => {
  if (!loading.value && !errorMessage.value && monitorData.value && !hasAnyPoint.value) {
    return '当前时间范围内暂无监测数据'
  }
  return ''
})
const overviewDeviceCode = computed(() => monitorData.value?.device_code || filters.deviceCode || '-')
const overviewStartTime = computed(() => monitorData.value?.start_time || filters.startTime || '-')
const overviewEndTime = computed(() => monitorData.value?.end_time || filters.endTime || '-')
const latestConditionLabel = computed(() => {
  const latestRow = seriesRows.value[seriesRows.value.length - 1]
  return latestRow?.condition_label || '-'
})
const statusTone = computed(() => {
  if (loading.value) return 'muted'
  if (errorMessage.value || validationMessage.value) return 'warning'
  if (monitorData.value && hasAnyPoint.value) return 'success'
  return 'default'
})
const statusLabel = computed(() => {
  if (loading.value) return '监测加载中'
  if (errorMessage.value || validationMessage.value) return '查询待处理'
  if (monitorData.value && hasAnyPoint.value) return '监测数据已接入'
  return '等待查询'
})
const statusDescription = computed(() => {
  if (loading.value) return '正在请求 /api/v1/monitor/history'
  if (errorMessage.value) return '接口请求失败，可检查后端服务状态后重试'
  if (validationMessage.value) return '请补齐设备编号和时间范围'
  if (monitorData.value) return `当前返回 ${pointCount.value} 个监测点`
  return '按设备编号与时间范围查询运行监测时序数据'
})

fetchDevices()
fetchMonitorHistory()

async function fetchDevices() {
  try {
    const result = await getDeviceList({ page: 1, size: 100 })
    const payload = result?.data && typeof result.data === 'object' ? result.data : result
    devices.value = Array.isArray(payload?.items)
      ? payload.items.filter((item) => item?.device_code)
      : []
  } catch (error) {
    devices.value = []
  }
}

async function fetchMonitorHistory() {
  const message = validateFilters()
  if (message) {
    validationMessage.value = message
    errorMessage.value = ''
    monitorData.value = null
    return
  }

  loading.value = true
  errorMessage.value = ''
  validationMessage.value = ''

  try {
    const result = await getMonitorHistory(buildApiParams())
    monitorData.value = normalizePayload(result)
  } catch (error) {
    monitorData.value = null
    errorMessage.value = error.message || '无法连接后端服务，请检查接口地址或后端是否已启动'
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  fetchMonitorHistory()
}

function handleReset() {
  Object.assign(filters, DEFAULT_FILTERS)
  fetchMonitorHistory()
}

function validateFilters() {
  if (!filters.deviceCode) return '设备编号不能为空'
  if (!filters.startTime) return '开始时间不能为空'
  if (!filters.endTime) return '结束时间不能为空'
  return ''
}

function buildApiParams() {
  return {
    device_code: filters.deviceCode,
    start_time: filters.startTime,
    end_time: filters.endTime,
    condition_label: filters.conditionLabel || undefined
  }
}

function normalizePayload(result) {
  const payload = result?.data && typeof result.data === 'object' ? result.data : result
  return {
    device_code: payload?.device_code || filters.deviceCode,
    start_time: payload?.start_time || filters.startTime,
    end_time: payload?.end_time || filters.endTime,
    count: payload?.count ?? 0,
    data_source: payload?.data_source || 'influxdb',
    series: Array.isArray(payload?.series) ? payload.series : []
  }
}

function normalizeQueryValue(value) {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0].trim() : ''
  }
  return typeof value === 'string' ? value.trim() : ''
}

function toNumberOrNull(value) {
  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}

function formatNumber(value) {
  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? numericValue.toFixed(2) : '-'
}

function formatCoordinate(row) {
  const lon = formatNumber(row.longitude)
  const lat = formatNumber(row.latitude)
  return lon === '-' && lat === '-' ? '-' : `${lon}, ${lat}`
}
</script>
