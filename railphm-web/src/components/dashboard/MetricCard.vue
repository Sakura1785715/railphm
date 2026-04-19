<template>
  <article class="metric-card">
    <div class="metric-card__header">
      <p class="metric-card__title">{{ title }}</p>
      <span v-if="badge" :class="['status-pill', badgeToneClass]">{{ badge }}</span>
    </div>

    <div v-if="loading" class="metric-card__body">
      <p class="metric-card__value">加载中...</p>
      <p class="metric-card__meta">正在获取最新数据</p>
    </div>

    <div v-else-if="error" class="metric-card__body">
      <p class="metric-card__value metric-card__value--error">加载失败</p>
      <p class="metric-card__meta">{{ error }}</p>
    </div>

    <div v-else class="metric-card__body">
      <p class="metric-card__value">{{ value }}</p>
      <p class="metric-card__meta">{{ description }}</p>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    default: '--'
  },
  description: {
    type: String,
    default: ''
  },
  badge: {
    type: String,
    default: ''
  },
  badgeTone: {
    type: String,
    default: 'default'
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

const badgeToneClass = computed(() => `status-pill--${props.badgeTone}`)
</script>
