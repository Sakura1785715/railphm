<template>
  <section class="device-table-card">
    <div class="device-table-card__header">
      <div>
        <p class="section-tag">设备列表</p>
        <h3>设备台账清单</h3>
        <p class="device-table-card__description">
          当前展示设备基础档案字段，支持查看单台设备详情，不扩展编辑与批量操作。
        </p>
      </div>

      <div class="device-table-card__meta">
        <span class="status-pill status-pill--default">共 {{ total }} 台设备</span>
        <span class="device-table-card__page">第 {{ page }} / {{ pageCount }} 页</span>
      </div>
    </div>

    <div v-if="error" class="state-panel error-state device-table-state">
      <h3>设备列表加载失败</h3>
      <p>{{ error }}</p>
      <button class="secondary-button" type="button" @click="$emit('retry')">重新加载</button>
    </div>

    <div v-else class="device-table-shell">
      <table class="device-table">
        <thead>
          <tr>
            <th>设备编号</th>
            <th>车号</th>
            <th>ATP 类型</th>
            <th>配属单位</th>
            <th>设备状态</th>
            <th>操作</th>
          </tr>
        </thead>

        <tbody v-if="loading">
          <tr>
            <td colspan="6" class="device-table__placeholder">正在加载设备台账数据...</td>
          </tr>
        </tbody>

        <tbody v-else-if="rows.length">
          <tr v-for="row in rows" :key="row.device_id">
            <td class="device-table__mono">{{ row.device_id }}</td>
            <td>{{ row.car_no || '未返回' }}</td>
            <td>{{ row.atp_type || '未返回' }}</td>
            <td>{{ row.attach_bureau || '未返回' }}</td>
            <td>
              <span :class="['status-pill', `status-pill--${getDeviceStatusMeta(row.device_status).tone}`]">
                {{ getDeviceStatusMeta(row.device_status).label }}
              </span>
            </td>
            <td>
              <RouterLink :to="buildDetailRoute(row.device_id)" class="table-link">
                查看详情
              </RouterLink>
            </td>
          </tr>
        </tbody>

        <tbody v-else>
          <tr>
            <td colspan="6" class="device-table__placeholder">{{ emptyText }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="device-table-footer">
      <p class="device-table-footer__summary">{{ rangeText }}</p>
      <div class="device-table-footer__actions">
        <button
          class="secondary-button"
          type="button"
          :disabled="loading || page <= 1"
          @click="$emit('page-change', page - 1)"
        >
          上一页
        </button>
        <button
          class="secondary-button"
          type="button"
          :disabled="loading || page >= pageCount || total === 0"
          @click="$emit('page-change', page + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { getDeviceStatusMeta } from '../../utils/dashboard'

const props = defineProps({
  rows: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  page: {
    type: Number,
    default: 1
  },
  size: {
    type: Number,
    default: 10
  },
  total: {
    type: Number,
    default: 0
  },
  emptyText: {
    type: String,
    default: '当前暂无设备数据。'
  },
  detailQuery: {
    type: Object,
    default: () => ({})
  }
})

defineEmits(['retry', 'page-change'])

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.size) || 1))

const rangeText = computed(() => {
  if (!props.total) {
    return '当前共 0 条记录'
  }

  if (!props.rows.length) {
    return `当前页暂无记录，共 ${props.total} 条记录`
  }

  const start = (props.page - 1) * props.size + 1
  const end = Math.min(props.total, start + props.rows.length - 1)

  return `当前显示 ${start}-${end} 条，共 ${props.total} 条记录`
})

function buildDetailRoute(deviceId) {
  return {
    name: 'device-detail',
    params: {
      id: deviceId
    },
    query: props.detailQuery
  }
}
</script>

<style scoped>
.device-table-card {
  display: grid;
  gap: 20px;
  padding: 24px 26px;
  background: #ffffff;
  border: 1px solid #d7e1ee;
  border-radius: 22px;
  box-shadow: 0 20px 42px rgba(15, 23, 42, 0.05);
}

.device-table-card__header,
.device-table-footer,
.device-table-card__meta,
.device-table-footer__actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.section-tag,
.device-table-card__description,
.device-table-footer__summary {
  margin: 0;
}

.section-tag {
  color: #0f6c85;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.device-table-card h3 {
  margin: 8px 0 0;
  color: #0f172a;
}

.device-table-card__description,
.device-table-card__page,
.device-table-footer__summary {
  color: #5b6d86;
}

.device-table-card__meta {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.device-table-shell {
  overflow-x: auto;
  border: 1px solid #deebf3;
  border-radius: 18px;
}

.device-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.device-table th,
.device-table td {
  padding: 16px 18px;
  border-bottom: 1px solid #e6eef5;
  text-align: left;
}

.device-table th {
  color: #45617f;
  font-size: 0.92rem;
  font-weight: 700;
  background: #f8fbfd;
}

.device-table tbody tr:hover {
  background: rgba(15, 108, 133, 0.04);
}

.device-table__mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-weight: 700;
}

.device-table__placeholder {
  padding: 44px 24px;
  color: #5b6d86;
  text-align: center;
}

.table-link {
  color: #0f6c85;
  font-weight: 700;
}

.table-link:hover {
  color: #1d4ed8;
}

.device-table-state {
  margin-top: 0;
}

.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #cfe0eb;
  background: rgba(255, 255, 255, 0.84);
  color: #0f6c85;
  cursor: pointer;
}

.secondary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .device-table-card {
    padding: 20px;
  }

  .device-table-card__header,
  .device-table-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .device-table-card__meta {
    justify-content: flex-start;
  }
}
</style>
