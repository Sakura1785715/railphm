<template>
  <header :class="['page-header', 'common-page-header', { 'common-page-header--compact': compact }]">
    <div class="common-page-header__main">
      <p v-if="eyebrow" class="page-tag">{{ eyebrow }}</p>
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="description" class="page-description">{{ description }}</p>
      <p v-if="meta" class="common-page-header__meta">{{ meta }}</p>
    </div>

    <div v-if="$slots.actions || $slots.default" class="page-actions common-page-header__actions">
      <slot name="actions">
        <slot />
      </slot>
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  eyebrow: {
    type: String,
    default: ''
  },
  meta: {
    type: String,
    default: ''
  },
  compact: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.common-page-header__main {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.common-page-header__meta {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.common-page-header--compact {
  padding: var(--space-5);
}

.common-page-header__actions {
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .common-page-header__actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
