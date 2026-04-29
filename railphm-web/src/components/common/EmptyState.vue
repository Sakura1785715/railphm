<template>
  <div class="empty-state common-empty-state">
    <div v-if="$slots.icon" class="common-empty-state__icon">
      <slot name="icon" />
    </div>
    <h3>{{ title }}</h3>
    <p v-if="description">{{ description }}</p>
    <div v-if="actionText || $slots.actions" class="common-empty-state__actions">
      <button v-if="actionText" class="secondary-button" type="button" @click="$emit('action')">
        {{ actionText }}
      </button>
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '暂无数据'
  },
  description: {
    type: String,
    default: ''
  },
  actionText: {
    type: String,
    default: ''
  }
})

defineEmits(['action'])
</script>

<style scoped>
.common-empty-state {
  display: grid;
  place-items: center;
  gap: var(--space-3);
  text-align: center;
}

.common-empty-state h3,
.common-empty-state p {
  margin: 0;
}

.common-empty-state h3 {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
}

.common-empty-state p {
  max-width: 560px;
  color: var(--color-text-secondary);
}

.common-empty-state__actions {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
</style>
