<template>
  <span :class="['dashboard-icon', `dashboard-icon--${tone}`, `dashboard-icon--${size}`]" aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path v-for="(path, index) in iconPaths" :key="index" :d="path" />
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: {
    type: String,
    default: 'home'
  },
  tone: {
    type: String,
    default: 'default'
  },
  size: {
    type: String,
    default: 'md'
  }
})

const iconMap = {
  home: ['M3 10.5L12 3l9 7.5', 'M5 9.5V21h14V9.5', 'M9 21v-6h6v6'],
  device: ['M7 4h10', 'M5 8h14', 'M7 12h10', 'M4 6v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6', 'M9 16h6'],
  monitor: ['M4 18h16', 'M7 14l3-4 3 2 4-5', 'M6 18V9', 'M18 18v-8'],
  prediction: ['M4 19l5-6 4 3 7-10', 'M4 5v14h16'],
  alert: ['M12 4l8 14H4L12 4z', 'M12 9v4', 'M12 17h.01'],
  health: ['M12 20s-7-4.35-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.65-7 10-7 10z', 'M10 11h4', 'M12 9v4'],
  service: ['M4 6h16', 'M4 12h16', 'M4 18h16', 'M7 9h.01', 'M7 15h.01'],
  risk: ['M12 3l7 4v5c0 5-3.5 8-7 9-3.5-1-7-4-7-9V7l7-4z', 'M12 8v4', 'M12 15h.01']
}

const iconPaths = computed(() => iconMap[props.name] || iconMap.home)
</script>

<style scoped>
.dashboard-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  border-radius: 14px;
}

.dashboard-icon svg {
  width: 18px;
  height: 18px;
}

.dashboard-icon--sm {
  width: 32px;
  height: 32px;
}

.dashboard-icon--md {
  width: 40px;
  height: 40px;
}

.dashboard-icon--lg {
  width: 48px;
  height: 48px;
}

.dashboard-icon--default {
  background: #eff4ff;
  color: #3154b5;
}

.dashboard-icon--success {
  background: rgba(22, 163, 74, 0.12);
  color: #15803d;
}

.dashboard-icon--warning {
  background: rgba(217, 119, 6, 0.12);
  color: #c2410c;
}

.dashboard-icon--danger {
  background: rgba(220, 38, 38, 0.12);
  color: #b91c1c;
}

.dashboard-icon--accent {
  background: rgba(8, 145, 178, 0.12);
  color: #0f6c85;
}
</style>
