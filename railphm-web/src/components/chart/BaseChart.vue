<template>
  <section class="base-chart-card">
    <div
      ref="chartEl"
      class="base-chart"
      :class="{ 'base-chart--hidden': shouldShowState }"
      :style="{ height: normalizedHeight }"
    />

    <div v-if="shouldShowState" class="base-chart__state" :style="{ minHeight: normalizedHeight }">
      <div class="base-chart__state-content">
        <span class="base-chart__state-dot" :class="stateClass" />
        <p>{{ stateText }}</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

const props = defineProps({
  option: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  },
  empty: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  height: {
    type: String,
    default: '320px'
  }
})

const chartEl = ref(null)
const chartInstance = shallowRef(null)
let resizeObserver = null

const normalizedHeight = computed(() => props.height || '320px')
const shouldShowState = computed(() => props.loading || props.empty || Boolean(props.error))
const stateText = computed(() => {
  if (props.error) {
    return `图表加载失败：${props.error}`
  }

  if (props.loading) {
    return '图表数据加载中...'
  }

  return '暂无可展示的图表数据'
})

const stateClass = computed(() => ({
  'base-chart__state-dot--loading': props.loading && !props.error,
  'base-chart__state-dot--empty': props.empty && !props.loading && !props.error,
  'base-chart__state-dot--error': Boolean(props.error)
}))

function ensureChart() {
  if (!chartEl.value || chartInstance.value) {
    return
  }

  chartInstance.value = echarts.init(chartEl.value, null, {
    renderer: 'canvas'
  })
}

function renderChart() {
  if (shouldShowState.value) {
    return
  }

  ensureChart()

  if (!chartInstance.value) {
    return
  }

  chartInstance.value.setOption(props.option || {}, true)
  chartInstance.value.resize()
}

function resizeChart() {
  if (chartInstance.value && !shouldShowState.value) {
    chartInstance.value.resize()
  }
}

function disposeChart() {
  if (chartInstance.value) {
    chartInstance.value.dispose()
    chartInstance.value = null
  }
}

onMounted(async () => {
  await nextTick()
  renderChart()
  window.addEventListener('resize', resizeChart)

  if (window.ResizeObserver && chartEl.value) {
    resizeObserver = new ResizeObserver(resizeChart)
    resizeObserver.observe(chartEl.value)
  }
})

watch(
  () => [props.loading, props.empty, props.error],
  async () => {
    await nextTick()

    if (shouldShowState.value) {
      disposeChart()
      return
    }

    renderChart()
  }
)

watch(
  () => props.option,
  async () => {
    await nextTick()
    renderChart()
  },
  { deep: true }
)

watch(normalizedHeight, async () => {
  await nextTick()
  resizeChart()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)

  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  disposeChart()
})
</script>

<style scoped>
.base-chart-card {
  position: relative;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--rail-border, #e1ddd4);
  border-radius: var(--rail-radius-lg, 22px);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(251, 250, 247, 0.94));
  box-shadow: var(--rail-shadow-md, 0 16px 34px rgba(23, 27, 31, 0.06));
}

.base-chart {
  width: 100%;
  min-width: 0;
}

.base-chart--hidden {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
}

.base-chart__state {
  display: grid;
  place-items: center;
  padding: 28px;
  color: var(--rail-text-muted, #667085);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(248, 246, 241, 0.78));
}

.base-chart__state-content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  max-width: 100%;
  text-align: center;
}

.base-chart__state-content p {
  margin: 0;
  overflow-wrap: anywhere;
  font-weight: 650;
}

.base-chart__state-dot {
  width: 10px;
  height: 10px;
  flex: 0 0 auto;
  border-radius: var(--rail-radius-pill, 999px);
  background: var(--rail-gray-soft, rgba(102, 112, 133, 0.12));
}

.base-chart__state-dot--loading {
  background: var(--rail-blue, #2f5f8f);
  box-shadow: 0 0 0 6px var(--rail-blue-soft, rgba(47, 95, 143, 0.1));
}

.base-chart__state-dot--empty {
  background: var(--rail-text-subtle, #8a93a3);
}

.base-chart__state-dot--error {
  background: var(--rail-red, #a24b3f);
  box-shadow: 0 0 0 6px var(--rail-red-soft, rgba(162, 75, 63, 0.13));
}
</style>

