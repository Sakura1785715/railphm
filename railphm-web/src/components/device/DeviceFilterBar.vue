<template>
  <section class="device-filter-card">
    <div class="device-filter-card__header">
      <div>
        <p class="section-tag">筛选查询</p>
        <h3>基础查询条件</h3>
      </div>
      <p class="device-filter-card__hint">按设备编号、车号和设备状态定位台账记录，点击查询后发起请求。</p>
    </div>

    <form class="device-filter-form" @submit.prevent="$emit('search')">
      <label class="filter-field">
        <span>设备编号</span>
        <input
          :value="deviceCode"
          type="search"
          placeholder="例如：ATP001"
          :disabled="loading"
          @input="$emit('update:deviceCode', $event.target.value)"
        />
      </label>

      <label class="filter-field">
        <span>车号</span>
        <input
          :value="carNo"
          type="search"
          placeholder="例如：CR400AF"
          :disabled="loading"
          @input="$emit('update:carNo', $event.target.value)"
        />
      </label>

      <label class="filter-field">
        <span>设备状态</span>
        <select
          :value="deviceStatus"
          :disabled="loading"
          @change="$emit('update:deviceStatus', $event.target.value)"
        >
          <option value="">全部</option>
          <option
            v-for="option in statusOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
      </label>

      <div class="filter-actions">
        <button class="primary-button" type="submit" :disabled="loading">
          {{ loading ? '查询中...' : '查询' }}
        </button>
        <button class="secondary-button" type="button" :disabled="loading" @click="$emit('reset')">
          重置
        </button>
      </div>
    </form>
  </section>
</template>

<script setup>
defineProps({
  deviceCode: {
    type: String,
    default: ''
  },
  carNo: {
    type: String,
    default: ''
  },
  deviceStatus: {
    type: String,
    default: ''
  },
  statusOptions: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:deviceCode', 'update:carNo', 'update:deviceStatus', 'search', 'reset'])
</script>

<style scoped>
.device-filter-card {
  display: grid;
  gap: 20px;
  padding: 24px 26px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
}

.device-filter-card__header,
.filter-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.section-tag,
.device-filter-card__hint,
.filter-field span {
  margin: 0;
}

.section-tag {
  color: var(--color-primary);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.device-filter-card h3 {
  margin: 8px 0 0;
  color: var(--color-text-primary);
}

.device-filter-card__hint {
  max-width: 360px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  text-align: right;
}

.device-filter-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 16px;
  align-items: end;
}

.filter-field {
  display: grid;
  gap: 8px;
}

.filter-field span {
  color: var(--color-text-secondary);
  font-size: 0.92rem;
  font-weight: 600;
}

.filter-field input,
.filter-field select {
  width: 100%;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
  color: var(--color-text-primary);
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.filter-field input:focus,
.filter-field select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(29, 79, 145, 0.12);
  background: var(--color-bg-panel);
}

.filter-field input:disabled,
.filter-field select:disabled {
  background: var(--color-neutral-soft);
  color: var(--color-text-muted);
  cursor: wait;
}

.filter-actions {
  gap: 12px;
}

@media (max-width: 1080px) {
  .device-filter-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .device-filter-card {
    padding: 20px;
  }

  .device-filter-card__header,
  .device-filter-form,
  .filter-actions {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: flex-start;
  }

  .device-filter-card__hint {
    max-width: none;
    text-align: left;
  }
}
</style>
