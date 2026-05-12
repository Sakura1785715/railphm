<template>
  <section :class="cardClass">
    <header v-if="hasHeader" class="section-card__header common-section-card__header">
      <div class="common-section-card__heading">
        <h3 v-if="title" class="section-card__title">{{ title }}</h3>
        <p v-if="description" class="section-description">{{ description }}</p>
      </div>
      <div v-if="$slots.headerActions" class="common-section-card__actions">
        <slot name="headerActions" />
      </div>
    </header>

    <div class="section-card__body">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="common-section-card__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script setup>
import { computed, useSlots } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  bordered: {
    type: Boolean,
    default: true
  },
  shadow: {
    type: Boolean,
    default: true
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const slots = useSlots()

const hasHeader = computed(() => Boolean(props.title || props.description || slots.headerActions))
const cardClass = computed(() => [
  'section-card',
  'common-section-card',
  {
    'common-section-card--plain': !props.bordered,
    'common-section-card--flat': !props.shadow,
    'common-section-card--compact': props.compact
  }
])
</script>

<style scoped>
.common-section-card__heading {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.common-section-card__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.common-section-card__footer {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.common-section-card--plain {
  border-color: transparent;
}

.common-section-card--flat {
  box-shadow: none;
}

.common-section-card--compact {
  gap: var(--space-4);
  padding: var(--space-5);
}

@media (max-width: 768px) {
  .common-section-card__actions {
    justify-content: flex-start;
  }
}
</style>
