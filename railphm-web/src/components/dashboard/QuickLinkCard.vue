<template>
  <RouterLink :to="item.to" class="quick-link-card">
    <div class="quick-link-card__header">
      <DashboardIcon :name="item.icon" tone="accent" />
      <span class="status-pill status-pill--muted">{{ item.statusText }}</span>
    </div>

    <div class="quick-link-card__body">
      <h3>{{ item.title }}</h3>
      <p>{{ item.description }}</p>
    </div>

    <div class="quick-link-card__footer">
      <span>{{ item.actionText }}</span>
      <span class="quick-link-card__arrow">›</span>
    </div>
  </RouterLink>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import DashboardIcon from './DashboardIcon.vue'

defineProps({
  item: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.quick-link-card {
  display: grid;
  gap: 18px;
  min-height: 168px;
  padding: 20px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbfd 100%);
  border: 1px solid #d8e3ee;
  border-radius: 18px;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.05);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.quick-link-card:hover {
  transform: translateY(-2px);
  border-color: #b8c7d9;
  box-shadow: 0 22px 40px rgba(15, 23, 42, 0.08);
}

.quick-link-card__header,
.quick-link-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.quick-link-card__body {
  display: grid;
  gap: 10px;
}

.quick-link-card__body h3,
.quick-link-card__body p {
  margin: 0;
}

.quick-link-card__body h3 {
  font-size: 1.05rem;
  color: #18253c;
}

.quick-link-card__body p {
  color: #5f7087;
  line-height: 1.65;
}

.quick-link-card__footer {
  color: #0f6c85;
  font-weight: 700;
}

.quick-link-card__arrow {
  font-size: 1.2rem;
  line-height: 1;
}
</style>
