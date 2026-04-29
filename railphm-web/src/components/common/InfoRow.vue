<template>
  <div class="common-info-row">
    <dt>{{ label }}</dt>
    <dd>
      <slot name="value">
        {{ displayValue }}
      </slot>
    </dd>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { normalizeDisplayValue } from '../../utils/status'

const props = defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    default: null
  },
  emptyText: {
    type: String,
    default: '--'
  }
})

const displayValue = computed(() => normalizeDisplayValue(props.value, props.emptyText))
</script>

<style scoped>
.common-info-row {
  display: grid;
  grid-template-columns: minmax(88px, 0.36fr) minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.common-info-row dt,
.common-info-row dd {
  margin: 0;
}

.common-info-row dt {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 690;
}

.common-info-row dd {
  min-width: 0;
  color: var(--color-text-primary);
  font-weight: 730;
  overflow-wrap: anywhere;
}

@media (max-width: 560px) {
  .common-info-row {
    grid-template-columns: 1fr;
    gap: var(--space-1);
  }
}
</style>
