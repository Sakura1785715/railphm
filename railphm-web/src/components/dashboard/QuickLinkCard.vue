<template>
  <article class="quick-link-card">
    <div class="quick-link-card__header">
      <div>
        <h3>{{ item.title }}</h3>
        <p>{{ item.description }}</p>
      </div>
      <span class="status-pill status-pill--muted">{{ item.statusText }}</span>
    </div>

    <RouterLink :to="item.to" class="text-link">
      {{ item.actionText }}
    </RouterLink>
  </article>
</template>

<script setup>
import { RouterLink } from 'vue-router'

defineProps({
  item: {
    type: Object,
    required: true
  }
})
</script>
