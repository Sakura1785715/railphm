<template>
  <section :class="['filter-panel', 'section-card', 'common-filter-panel', { 'common-filter-panel--collapsed': collapsed }]">
    <header v-if="title || description || $slots.headerActions" class="section-card__header common-filter-panel__header">
      <div class="common-filter-panel__heading">
        <p v-if="eyebrow" class="section-tag">{{ eyebrow }}</p>
        <h3 v-if="title" class="section-card__title">{{ title }}</h3>
        <p v-if="description" class="section-description">{{ description }}</p>
      </div>
      <div v-if="$slots.headerActions" class="common-filter-panel__header-actions">
        <slot name="headerActions" />
      </div>
    </header>

    <div v-if="!collapsed" class="common-filter-panel__body">
      <slot />
    </div>

    <ActionBar v-if="$slots.actions && !collapsed" class="common-filter-panel__actions">
      <slot name="actions" />
    </ActionBar>
  </section>
</template>

<script setup>
import ActionBar from './ActionBar.vue'

defineProps({
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  eyebrow: {
    type: String,
    default: ''
  },
  collapsed: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.common-filter-panel {
  gap: var(--space-5);
}

.common-filter-panel__heading,
.common-filter-panel__body {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}

.common-filter-panel__header-actions {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.common-filter-panel__actions {
  margin-top: 0;
}
</style>
