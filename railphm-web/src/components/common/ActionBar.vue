<template>
  <div :class="barClass">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  align: {
    type: String,
    default: 'right'
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const barClass = computed(() => [
  'action-bar',
  'common-action-bar',
  `common-action-bar--${props.align}`,
  {
    'common-action-bar--compact': props.compact
  }
])
</script>

<style scoped>
.common-action-bar--left {
  justify-content: flex-start;
}

.common-action-bar--right {
  justify-content: flex-end;
}

.common-action-bar--between {
  justify-content: space-between;
}

.common-action-bar--compact {
  gap: var(--space-2);
}

@media (max-width: 768px) {
  .common-action-bar {
    justify-content: flex-start;
  }
}
</style>
