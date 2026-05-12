<template>
  <span :class="tagClass">
    {{ displayLabel }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { resolveStatusMeta } from '../../utils/status'

const props = defineProps({
  value: {
    type: [String, Number],
    default: ''
  },
  type: {
    type: String,
    default: ''
  },
  label: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'default'
  },
  variant: {
    type: String,
    default: 'soft'
  }
})

const meta = computed(() => resolveStatusMeta(props.value, props.type, props.label))
const displayLabel = computed(() => meta.value.label)
const tagClass = computed(() => [
  'status-tag',
  'common-tag',
  `common-tag--${meta.value.type}`,
  `common-tag--${props.variant}`,
  {
    'common-tag--small': props.size === 'small'
  }
])
</script>

<style scoped>
.common-tag--small {
  min-height: 24px;
  padding: 0 8px;
  font-size: 0.7rem;
}

.common-tag--success {
  background: var(--color-success-soft);
  border-color: var(--color-success-border);
  color: var(--color-success);
}

.common-tag--warning {
  background: var(--color-warning-soft);
  border-color: var(--color-warning-border);
  color: var(--color-warning);
}

.common-tag--danger {
  background: var(--color-danger-soft);
  border-color: var(--color-danger-border);
  color: var(--color-danger);
}

.common-tag--info,
.common-tag--primary {
  background: var(--color-info-soft);
  border-color: var(--color-info-border);
  color: var(--color-info);
}

.common-tag--neutral,
.common-tag--muted,
.common-tag--default {
  background: var(--color-neutral-soft);
  border-color: var(--color-neutral-border);
  color: var(--color-neutral);
}

.common-tag--outline {
  background: transparent;
}

.common-tag--solid.common-tag--success {
  background: var(--color-success);
  border-color: var(--color-success);
  color: var(--color-text-inverse);
}

.common-tag--solid.common-tag--warning {
  background: var(--color-warning);
  border-color: var(--color-warning);
  color: var(--color-text-inverse);
}

.common-tag--solid.common-tag--danger {
  background: var(--color-danger);
  border-color: var(--color-danger);
  color: var(--color-text-inverse);
}

.common-tag--solid.common-tag--info,
.common-tag--solid.common-tag--primary {
  background: var(--color-info);
  border-color: var(--color-info);
  color: var(--color-text-inverse);
}

.common-tag--solid.common-tag--neutral,
.common-tag--solid.common-tag--muted,
.common-tag--solid.common-tag--default {
  background: var(--color-neutral);
  border-color: var(--color-neutral);
  color: var(--color-text-inverse);
}
</style>
