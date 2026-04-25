<template>
  <article class="line-trend-chart">
    <header v-if="title || description" class="line-trend-chart__header">
      <div>
        <h3 v-if="title">{{ title }}</h3>
        <p v-if="description">{{ description }}</p>
      </div>
      <span v-if="unit" class="line-trend-chart__unit">{{ unit }}</span>
    </header>

    <BaseChart
      :option="chartOption"
      :loading="loading"
      :empty="isEmpty"
      :error="error"
      :height="height"
    />
  </article>
</template>

<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import {
  axisLineStyle,
  chartColors,
  chartGrid,
  chartTextStyle,
  chartTooltipStyle,
  splitLineStyle
} from './chartTheme'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  xAxisData: {
    type: Array,
    default: () => []
  },
  series: {
    type: Array,
    default: () => []
  },
  unit: {
    type: String,
    default: ''
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

const hasSeriesData = computed(() =>
  props.series.some((item) => Array.isArray(item.data) && item.data.length > 0)
)

const isEmpty = computed(() => props.empty || props.xAxisData.length === 0 || !hasSeriesData.value)

function escapeTooltipText(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }

    return entities[char]
  })
}

const chartOption = computed(() => ({
  color: chartColors,
  textStyle: chartTextStyle,
  animationDuration: 360,
  tooltip: {
    ...chartTooltipStyle,
    formatter: (params) => {
      const items = Array.isArray(params) ? params : [params]
      const title = escapeTooltipText(items[0]?.axisValueLabel || '')
      const rows = items
        .map((item) => {
          const source = props.series[item.seriesIndex] || {}
          const seriesUnit = source.unit || props.unit
          const value = item.value === null || item.value === undefined || item.value === '' ? '-' : item.value
          const displayValue = seriesUnit && value !== '-' ? `${value} ${seriesUnit}` : value

          return `${item.marker}<span>${escapeTooltipText(item.seriesName)}</span><strong style="float:right;margin-left:18px;color:#0f172a;">${escapeTooltipText(displayValue)}</strong>`
        })
        .join('<br/>')

      return `<div style="min-width:140px;"><div style="margin-bottom:6px;color:#667085;">${title}</div>${rows}</div>`
    }
  },
  legend: {
    top: 8,
    right: 8,
    icon: 'roundRect',
    itemWidth: 16,
    itemHeight: 8,
    textStyle: {
      color: '#667085',
      fontSize: 12
    }
  },
  grid: chartGrid,
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.xAxisData,
    axisLine: axisLineStyle,
    axisTick: {
      show: false
    },
    axisLabel: {
      color: '#8a93a3',
      hideOverlap: true,
      margin: 14
    }
  },
  yAxis: {
    type: 'value',
    name: props.unit,
    nameTextStyle: {
      color: '#8a93a3',
      align: 'right',
      padding: [0, 4, 6, 0]
    },
    axisLine: {
      show: false
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      color: '#8a93a3'
    },
    splitLine: splitLineStyle
  },
  series: props.series.map((item, index) => ({
    name: item.name || `指标 ${index + 1}`,
    type: 'line',
    data: item.data || [],
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    showSymbol: false,
    emphasis: {
      focus: 'series'
    },
    lineStyle: {
      width: 2.5
    },
    areaStyle: item.area
      ? {
          opacity: 0.08
        }
      : undefined
  }))
}))
</script>

<style scoped>
.line-trend-chart {
  display: grid;
  min-width: 0;
  gap: 14px;
}

.line-trend-chart__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.line-trend-chart__header h3 {
  margin: 0;
  color: var(--rail-text-strong, #0f172a);
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}

.line-trend-chart__header p {
  margin: 6px 0 0;
  color: var(--rail-text-muted, #667085);
  line-height: 1.7;
}

.line-trend-chart__unit {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  flex: 0 0 auto;
  border: 1px solid var(--rail-border, #e1ddd4);
  border-radius: var(--rail-radius-pill, 999px);
  background: rgba(255, 255, 255, 0.62);
  color: var(--rail-text-muted, #667085);
  font-size: 0.78rem;
  font-weight: 720;
}

@media (max-width: 768px) {
  .line-trend-chart__header {
    display: grid;
  }
}
</style>
