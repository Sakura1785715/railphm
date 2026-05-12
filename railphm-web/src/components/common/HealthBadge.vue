<template>
  <span :class="badgeClass">
    <template v-if="meta.score === null">
      {{ meta.label }}
    </template>
    <template v-else>
      {{ meta.valueText }}<span v-if="showUnit">%</span>
      <span v-if="showLevel" class="common-health-badge__level">{{ meta.label }}</span>
    </template>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { resolveHealthMeta } from '../../utils/status'

const props = defineProps({
  score: {
    type: [Number, String],
    default: null
  },
  showLevel: {
    type: Boolean,
    default: true
  },
  showUnit: {
    type: Boolean,
    default: true
  },
  size: {
    type: String,
    default: 'default'
  }
})

const meta = computed(() => resolveHealthMeta(props.score))
const badgeClass = computed(() => [
  'health-badge',
  `is-${meta.value.type}`,
  `health-${meta.value.type}`,
  {
    'common-health-badge--small': props.size === 'small'
  }
])
</script>

<style scoped>
.common-health-badge__level {
  margin-left: var(--space-2);
}

.common-health-badge--small {
  min-height: 24px;
  padding: 0 8px;
  font-size: 0.7rem;
}
</style>
