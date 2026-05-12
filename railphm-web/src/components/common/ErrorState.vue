<template>
  <div class="error-state common-error-state">
    <div>
      <h3>{{ title }}</h3>
      <p v-if="message">{{ message }}</p>
      <slot />
    </div>
    <button v-if="showRetry" class="secondary-button" type="button" @click="$emit('retry')">
      {{ retryText }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '加载失败'
  },
  message: {
    type: String,
    default: ''
  },
  retryText: {
    type: String,
    default: '重试'
  },
  showRetry: {
    type: Boolean,
    default: true
  }
})

defineEmits(['retry'])
</script>

<style scoped>
.common-error-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.common-error-state h3,
.common-error-state p {
  margin: 0;
}

.common-error-state h3 {
  color: var(--color-danger);
  font-size: var(--font-size-base);
}

.common-error-state p {
  margin-top: var(--space-2);
}

@media (max-width: 768px) {
  .common-error-state {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
