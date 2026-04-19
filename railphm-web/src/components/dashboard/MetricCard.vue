<template>
  <article :class="['metric-card', `metric-card--${tone}`, { 'metric-card--emphasis': emphasis }]">
    <div class="metric-card__header">
      <div class="metric-card__title-wrap">
        <p class="metric-card__eyebrow">{{ eyebrow }}</p>
        <p class="metric-card__title">{{ title }}</p>
      </div>

      <div class="metric-card__header-meta">
        <span v-if="badge" :class="['status-pill', badgeToneClass]">{{ badge }}</span>
        <DashboardIcon :name="icon" :tone="iconTone" />
      </div>
    </div>

    <div v-if="loading" class="metric-card__body">
      <span class="metric-card__skeleton metric-card__skeleton--value"></span>
      <span class="metric-card__skeleton metric-card__skeleton--meta"></span>
      <span class="metric-card__skeleton metric-card__skeleton--meta metric-card__skeleton--short"></span>
    </div>

    <div v-else-if="error" class="metric-card__body">
      <p class="metric-card__value metric-card__value--error">暂不可用</p>
      <p class="metric-card__meta">{{ error }}</p>
    </div>

    <div v-else class="metric-card__body">
      <div class="metric-card__value-row">
        <p class="metric-card__value">{{ value }}</p>
        <span v-if="valueSuffix" class="metric-card__value-suffix">{{ valueSuffix }}</span>
      </div>
      <p class="metric-card__meta">{{ description }}</p>
      <p v-if="helper" class="metric-card__helper">{{ helper }}</p>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import DashboardIcon from './DashboardIcon.vue'

const props = defineProps({
  eyebrow: {
    type: String,
    default: '首页指标'
  },
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
  helper: {
    type: String,
    default: ''
  },
  valueSuffix: {
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
  },
  tone: {
    type: String,
    default: 'default'
  },
  icon: {
    type: String,
    default: 'service'
  },
  iconTone: {
    type: String,
    default: 'accent'
  },
  emphasis: {
    type: Boolean,
    default: false
  }
})

const badgeToneClass = computed(() => `status-pill--${props.badgeTone}`)
</script>

<style scoped>
.metric-card {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 18px;
  min-height: 196px;
  padding: 22px 24px;
  background: #ffffff;
  border: 1px solid #d7e1ee;
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
}

.metric-card::before {
  content: '';
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 3px;
  background: transparent;
}

.metric-card--success::before {
  background: linear-gradient(90deg, #16a34a 0%, #86efac 100%);
}

.metric-card--warning::before {
  background: linear-gradient(90deg, #d97706 0%, #fdba74 100%);
}

.metric-card--danger::before {
  background: linear-gradient(90deg, #dc2626 0%, #fca5a5 100%);
}

.metric-card--focus::before {
  background: linear-gradient(90deg, #0f6c85 0%, #38bdf8 100%);
}

.metric-card--emphasis {
  box-shadow: 0 22px 48px rgba(15, 23, 42, 0.08);
}

.metric-card__header,
.metric-card__header-meta,
.metric-card__value-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.metric-card__title-wrap {
  display: grid;
  gap: 6px;
}

.metric-card__eyebrow,
.metric-card__title,
.metric-card__meta,
.metric-card__helper {
  margin: 0;
}

.metric-card__eyebrow {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7b8aa0;
  font-weight: 700;
}

.metric-card__title {
  color: #20324d;
  font-size: 1rem;
  font-weight: 600;
}

.metric-card__header-meta {
  align-items: center;
}

.metric-card__body {
  display: grid;
  gap: 10px;
}

.metric-card__value-row {
  justify-content: flex-start;
  align-items: baseline;
}

.metric-card__value {
  margin: 0;
  font-size: clamp(2rem, 2.4vw, 2.6rem);
  font-weight: 700;
  line-height: 1;
  color: #0f172a;
}

.metric-card__value--error {
  font-size: 1.3rem;
  color: #b91c1c;
}

.metric-card__value-suffix {
  color: #64748b;
  font-size: 0.95rem;
  font-weight: 600;
}

.metric-card__meta {
  color: #52637b;
  line-height: 1.6;
}

.metric-card__helper {
  color: #8191a7;
  font-size: 0.92rem;
}

.metric-card__skeleton {
  display: inline-flex;
  width: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #edf2f8 0%, #f8fbfd 50%, #edf2f8 100%);
  background-size: 200% 100%;
  animation: metric-shimmer 1.5s linear infinite;
}

.metric-card__skeleton--value {
  height: 34px;
  width: 46%;
}

.metric-card__skeleton--meta {
  height: 14px;
}

.metric-card__skeleton--short {
  width: 62%;
}

@keyframes metric-shimmer {
  from {
    background-position: 200% 0;
  }

  to {
    background-position: -200% 0;
  }
}
</style>
