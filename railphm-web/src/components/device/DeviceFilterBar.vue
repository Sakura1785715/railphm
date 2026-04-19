<template>
  <section class="device-filter-card">
    <div class="device-filter-card__header">
      <div>
        <p class="section-tag">最小筛选</p>
        <h3>基础查询条件</h3>
      </div>
      <p class="device-filter-card__hint">当前筛选直接使用设备列表真实接口，不扩展高级检索能力。</p>
    </div>

    <form class="device-filter-form" @submit.prevent="$emit('search')">
      <label class="filter-field">
        <span>设备编号</span>
        <input
          :value="deviceId"
          type="search"
          inputmode="numeric"
          placeholder="请输入设备编号"
          @input="$emit('update:deviceId', $event.target.value)"
        />
      </label>

      <label class="filter-field">
        <span>车号</span>
        <input
          :value="carNo"
          type="search"
          placeholder="请输入车号"
          @input="$emit('update:carNo', $event.target.value)"
        />
      </label>

      <label class="filter-field">
        <span>设备状态</span>
        <select
          :value="deviceStatus"
          @change="$emit('update:deviceStatus', $event.target.value)"
        >
          <option value="">全部状态</option>
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
  deviceId: {
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

defineEmits(['update:deviceId', 'update:carNo', 'update:deviceStatus', 'search', 'reset'])
</script>

<style scoped>
.device-filter-card {
  display: grid;
  gap: 20px;
  padding: 24px 26px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbfd 100%);
  border: 1px solid #d7e1ee;
  border-radius: 22px;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.05);
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
  color: #0f6c85;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.device-filter-card h3 {
  margin: 8px 0 0;
  color: #0f172a;
}

.device-filter-card__hint {
  max-width: 360px;
  color: #5b6d86;
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
  color: #45617f;
  font-size: 0.92rem;
  font-weight: 600;
}

.filter-field input,
.filter-field select {
  width: 100%;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid #cfe0eb;
  border-radius: 12px;
  background: #f8fbfd;
  color: #17253a;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.filter-field input:focus,
.filter-field select:focus {
  border-color: #0f6c85;
  box-shadow: 0 0 0 4px rgba(15, 108, 133, 0.12);
  background: #ffffff;
}

.filter-actions {
  gap: 12px;
}

.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 18px;
  border-radius: 12px;
  border: 1px solid #cfe0eb;
  background: rgba(255, 255, 255, 0.84);
  color: #0f6c85;
  cursor: pointer;
}

.secondary-button:disabled {
  opacity: 0.72;
  cursor: wait;
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
