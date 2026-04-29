<template>
  <article :class="['stat-card', 'common-stat-card', `common-stat-card--${tone}`]">
    <div v-if="$slots.icon || type !== 'default'" class="common-stat-card__top">
      <slot name="icon">
        <span class="common-stat-card__dot" aria-hidden="true"></span>
      </slot>
    </div>

    <span class="stat-card__label">{{ label }}</span>

    <strong class="stat-card__value">
      <span v-if="loading" class="common-stat-card__skeleton">--</span>
      <template v-else>
        {{ displayValue }}<small v-if="unit">{{ unit }}</small>
      </template>
    </strong>

    <p v-if="description" class="stat-card__desc">{{ description }}</p>
    <p v-if="trend" class="common-stat-card__trend">{{ trend }}</p>
    <div v-if="$slots.extra" class="common-stat-card__extra">
      <slot name="extra" />
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { normalizeDisplayValue, normalizeTone } from '../../utils/status'

const props = defineProps({
  label: {
    type: String,
    default: ''
  },
  value: {
    type: [String, Number],
    default: null
  },
  unit: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  trend: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: 'default'
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const tone = computed(() => normalizeTone(props.type) || 'default')
const displayValue = computed(() => normalizeDisplayValue(props.value))
</script>

<style scoped>
.common-stat-card {
  position: relative;
  overflow: hidden;
}

.common-stat-card__top {
  display: flex;
  justify-content: flex-end;
}

.common-stat-card__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-pill);
  background: var(--stat-color, var(--color-neutral));
}

.stat-card__value small {
  margin-left: var(--space-1);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 700;
}

.common-stat-card__trend {
  margin: 0;
  color: var(--stat-color, var(--color-text-secondary));
  font-size: var(--font-size-sm);
  font-weight: 700;
}

.common-stat-card__extra {
  margin-top: var(--space-2);
}

.common-stat-card--primary {
  --stat-color: var(--color-primary);
  border-color: var(--color-primary-border);
}

.common-stat-card--success {
  --stat-color: var(--color-success);
  border-color: var(--color-success-border);
}

.common-stat-card--warning {
  --stat-color: var(--color-warning);
  border-color: var(--color-warning-border);
}

.common-stat-card--danger {
  --stat-color: var(--color-danger);
  border-color: var(--color-danger-border);
}

.common-stat-card--info {
  --stat-color: var(--color-info);
  border-color: var(--color-info-border);
}

.common-stat-card--neutral,
.common-stat-card--muted {
  --stat-color: var(--color-neutral);
}

.common-stat-card__skeleton {
  color: var(--color-text-muted);
}
</style>
