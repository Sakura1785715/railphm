<template>
  <LineTrendChart
    :title="title"
    :description="description"
    :x-axis-data="xAxisData"
    :series="trendSeries"
    :unit="unit"
    :loading="loading"
    :empty="isEmpty"
    :error="error"
    :height="height"
  />
</template>

<script setup>
import { computed } from 'vue'
import LineTrendChart from './LineTrendChart.vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  metricName: {
    type: String,
    default: '指标'
  },
  unit: {
    type: String,
    default: ''
  },
  points: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  height: {
    type: String,
    default: '300px'
  }
})

const xAxisData = computed(() => props.points.map((point) => point.time))
const trendSeries = computed(() => [
  {
    name: props.metricName,
    data: props.points.map((point) => point.value),
    unit: props.unit,
    area: true
  }
])
const isEmpty = computed(() => props.points.length === 0)
</script>

