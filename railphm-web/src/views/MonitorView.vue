<template>
  <section class="monitor-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">运行监测</p>
        <h2>设备运行监测</h2>
        <p class="page-description">
          按设备编号和时间范围查询 ATP 车载监测数据，展示速度、里程、运行距离等后端返回的监测指标。
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
          <p>默认参数用于匹配当前后端 mock 数据，可按实际设备和时间范围调整。</p>
        </div>
      </div>

      <div class="monitor-filter-grid">
        <label class="filter-field">
          <span>设备编号</span>
          <input v-model.trim="filters.deviceId" type="text" placeholder="1" :disabled="loading" />
        </label>

        <label class="filter-field">
          <span>开始时间</span>
          <input
            v-model.trim="filters.startTime"
            type="text"
            placeholder="2015-01-09 10:20:00"
            :disabled="loading"
          />
        </label>

        <label class="filter-field">
          <span>结束时间</span>
          <input
            v-model.trim="filters.endTime"
            type="text"
            placeholder="2015-01-09 10:25:00"
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
        <strong>{{ overviewDeviceId }}</strong>
      </article>
      <article class="monitor-overview-card">
        <span>开始时间</span>
        <strong>{{ overviewStartTime }}</strong>
      </article>
      <article class="monitor-overview-card">
        <span>结束时间</span>
        <strong>{{ overviewEndTime }}</strong>
      </article>
      <article class="monitor-overview-card">
        <span>指标 / 点位</span>
        <strong>{{ metricCount }} / {{ pointCount }}</strong>
      </article>
    </div>

    <section class="monitor-section">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">动态指标</p>
          <h3>后端返回指标</h3>
        </div>
        <p>当前页面完全基于后端 /api/v1/monitor/series 返回的 series 字段动态渲染。</p>
      </div>

      <div class="monitor-metric-list">
        <span v-for="item in normalizedSeries" :key="item.metric || item.name" class="monitor-metric-chip">
          {{ item.name || item.metric || '未命名指标' }}
          <small v-if="item.unit">{{ item.unit }}</small>
        </span>
        <span v-if="normalizedSeries.length === 0" class="monitor-metric-chip monitor-metric-chip--muted">
          暂无后端返回指标
        </span>
      </div>
    </section>

    <LineTrendChart
      title="多指标趋势总览"
      description="将后端返回的所有 series 组合展示；不同指标缺失的时间点以空值保留。"
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
          <p class="section-tag">单指标趋势</p>
          <h3>逐指标监测曲线</h3>
        </div>
        <p>后端返回几个指标，页面就生成几个单指标图表，不预设固定指标数量。</p>
      </div>

      <div class="monitor-chart-grid">
        <MetricTrendChart
          v-for="item in normalizedSeries"
          :key="item.metric || item.name"
          :title="item.name || item.metric || '未命名指标'"
          :description="buildMetricDescription(item)"
          :metric-name="item.name || item.metric || '指标'"
          :unit="item.unit || ''"
          :points="item.points"
          :loading="loading"
          :error="errorMessage"
          height="300px"
        />
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { LineTrendChart, MetricTrendChart } from '../components/chart'
import { getMonitorSeries } from '../api/monitor'

const DEFAULT_FILTERS = {
  deviceId: '1',
  startTime: '2015-01-09 10:20:00',
  endTime: '2015-01-09 10:25:00'
}

const filters = reactive({ ...DEFAULT_FILTERS })
const monitorData = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const validationMessage = ref('')

const normalizedSeries = computed(() => {
  const series = monitorData.value?.series

  if (!Array.isArray(series)) {
    return []
  }

  return series.map((item) => ({
    metric: item?.metric || '',
    name: item?.name || item?.metric || '',
    unit: item?.unit || '',
    points: Array.isArray(item?.points)
      ? item.points
          .filter((point) => point && point.time !== undefined)
          .map((point) => ({
            time: point.time,
            value: point.value ?? null
          }))
      : []
  }))
})

const overviewXAxisData = computed(() => {
  const times = new Set()

  normalizedSeries.value.forEach((item) => {
    item.points.forEach((point) => {
      times.add(point.time)
    })
  })

  return Array.from(times).sort()
})

const overviewChartSeries = computed(() =>
  normalizedSeries.value.map((item) => {
    const valueMap = new Map(item.points.map((point) => [point.time, point.value]))

    return {
      name: item.name || item.metric || '未命名指标',
      unit: item.unit || '',
      data: overviewXAxisData.value.map((time) => (valueMap.has(time) ? valueMap.get(time) : null))
    }
  })
)

const metricCount = computed(() => normalizedSeries.value.length)
const pointCount = computed(() =>
  normalizedSeries.value.reduce((total, item) => total + item.points.length, 0)
)
const hasAnyPoint = computed(() => pointCount.value > 0)
const emptyMessage = computed(() => {
  if (!loading.value && !errorMessage.value && monitorData.value && !hasAnyPoint.value) {
    return '当前时间范围内暂无运行监测数据'
  }

  return ''
})

const overviewDeviceId = computed(() => (monitorData.value?.device_id ?? filters.deviceId) || '-')
const overviewStartTime = computed(() => monitorData.value?.start_time || filters.startTime || '-')
const overviewEndTime = computed(() => monitorData.value?.end_time || filters.endTime || '-')

const statusTone = computed(() => {
  if (loading.value) {
    return 'muted'
  }

  if (errorMessage.value || validationMessage.value) {
    return 'warning'
  }

  if (monitorData.value && hasAnyPoint.value) {
    return 'success'
  }

  return 'default'
})

const statusLabel = computed(() => {
  if (loading.value) {
    return '监测加载中'
  }

  if (errorMessage.value || validationMessage.value) {
    return '查询待处理'
  }

  if (monitorData.value && hasAnyPoint.value) {
    return '监测数据已接入'
  }

  return '等待查询'
})

const statusDescription = computed(() => {
  if (loading.value) {
    return '正在请求 /api/v1/monitor/series'
  }

  if (errorMessage.value) {
    return '接口请求失败，可检查后端服务状态后重试'
  }

  if (validationMessage.value) {
    return '请补齐设备编号和时间范围'
  }

  if (monitorData.value) {
    return `当前返回 ${metricCount.value} 个指标，${pointCount.value} 个有效点位`
  }

  return '按设备编号与时间范围查询运行监测时序数据'
})

fetchMonitorSeries()

async function fetchMonitorSeries() {
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
    const result = await getMonitorSeries(buildApiParams())
    monitorData.value = normalizePayload(result)
  } catch (error) {
    monitorData.value = null
    errorMessage.value = error.message || '无法连接后端服务，请检查接口地址或后端是否已启动'
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  fetchMonitorSeries()
}

function handleReset() {
  Object.assign(filters, DEFAULT_FILTERS)
  fetchMonitorSeries()
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

  return ''
}

function buildApiParams() {
  return {
    device_id: filters.deviceId,
    start_time: filters.startTime,
    end_time: filters.endTime
  }
}

function normalizePayload(result) {
  const payload = result?.data && typeof result.data === 'object' ? result.data : result

  return {
    device_id: payload?.device_id ?? filters.deviceId,
    start_time: payload?.start_time || filters.startTime,
    end_time: payload?.end_time || filters.endTime,
    series: Array.isArray(payload?.series) ? payload.series : []
  }
}

function buildMetricDescription(item) {
  const count = item.points.length
  const unitText = item.unit ? `，单位 ${item.unit}` : ''

  return `后端指标 ${item.metric || item.name || '未命名'}${unitText}，当前 ${count} 个点位。`
}
</script>
