<template>
  <div :class="['loading-block', 'common-loading-block', `common-loading-block--${type}`]" :style="blockStyle">
    <span class="common-loading-block__indicator" aria-hidden="true"></span>
    <span>{{ text || '正在加载...' }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  text: {
    type: String,
    default: '正在加载...'
  },
  height: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: 'block'
  }
})

const blockStyle = computed(() => (props.height ? { minHeight: props.height } : {}))
</script>

<style scoped>
.common-loading-block {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}

.common-loading-block__indicator {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-pill);
  background: var(--color-info);
  box-shadow: 0 0 0 5px var(--color-info-soft);
}

.common-loading-block--inline {
  display: inline-flex;
  padding: 0;
  border: 0;
  background: transparent;
}

.common-loading-block--page {
  min-height: 240px;
}
</style>
