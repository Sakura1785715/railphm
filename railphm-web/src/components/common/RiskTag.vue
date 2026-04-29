<template>
  <span :class="tagClass">
    <template v-if="showText">{{ meta.label }}</template>
    <template v-else>{{ meta.level }}</template>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { resolveRiskMeta } from '../../utils/status'

const props = defineProps({
  level: {
    type: String,
    default: ''
  },
  score: {
    type: [Number, String],
    default: null
  },
  showText: {
    type: Boolean,
    default: true
  },
  size: {
    type: String,
    default: 'default'
  }
})

const meta = computed(() => resolveRiskMeta(props.level, props.score))
const tagClass = computed(() => [
  'risk-tag',
  `is-${meta.value.type}`,
  `risk-${meta.value.level.toLowerCase()}`,
  {
    'common-risk-tag--small': props.size === 'small'
  }
])
</script>

<style scoped>
.common-risk-tag--small {
  min-height: 24px;
  padding: 0 8px;
  font-size: 0.7rem;
}
</style>
