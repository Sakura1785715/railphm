<template>
  <section class="device-table-card">
    <div class="device-table-card__header">
      <div>
        <p class="section-tag">设备列表</p>
        <h3>设备台账清单</h3>
        <p class="device-table-card__description">
          当前展示设备基础档案字段，支持查看详情与维护设备基础信息。
        </p>
      </div>

      <div class="device-table-card__meta">
        <span class="status-pill status-pill--default">共 {{ total }} 台设备</span>
        <span class="device-table-card__page">第 {{ page }} / {{ pageCount }} 页</span>
      </div>
    </div>

    <div v-if="error" class="state-panel error-state device-table-state">
      <ErrorState title="设备列表加载失败" :message="error" retry-text="重新加载" @retry="$emit('retry')" />
    </div>

    <div v-else class="device-table-shell">
      <table class="device-table">
        <thead>
          <tr>
            <th>设备 ID</th>
            <th>车号</th>
            <th>ATP 类型</th>
            <th>配属铁路局</th>
            <th>设备状态</th>
            <th>操作</th>
          </tr>
        </thead>

        <tbody v-if="loading">
          <tr>
            <td colspan="6" class="device-table__placeholder">
              <LoadingBlock text="正在加载设备台账数据..." type="inline" />
            </td>
          </tr>
        </tbody>

        <tbody v-else-if="rows.length">
          <tr v-for="row in rows" :key="row.device_id">
            <td class="device-table__mono">{{ row.device_id }}</td>
            <td>{{ row.car_no || '未返回' }}</td>
            <td>{{ row.atp_type || '未返回' }}</td>
            <td>{{ row.attach_bureau || '未返回' }}</td>
            <td>
              <StatusTag
                :label="getDeviceStatusMeta(row.device_status).label"
                :type="getDeviceStatusMeta(row.device_status).tone"
                size="small"
              />
            </td>
            <td>
              <div class="device-table__actions">
                <RouterLink :to="buildDetailRoute(row.device_id)" class="table-link">
                  查看详情
                </RouterLink>
                <button
                  v-if="canEdit"
                  class="table-action-button"
                  type="button"
                  @click="$emit('edit', row)"
                >
                  编辑
                </button>
              </div>
            </td>
          </tr>
        </tbody>

        <tbody v-else>
          <tr>
            <td colspan="6" class="device-table__placeholder">
              <EmptyState title="暂无设备数据" :description="emptyText" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="device-table-footer">
      <p class="device-table-footer__summary">{{ rangeText }}</p>
      <div class="device-table-footer__actions">
        <label class="device-table-footer__size">
          <span>每页</span>
          <select
            :value="size"
            :disabled="loading"
            @change="$emit('size-change', Number($event.target.value))"
          >
            <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }} 条</option>
          </select>
        </label>
        <span class="device-table-card__page">第 {{ page }} / {{ pageCount }} 页</span>
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
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import LoadingBlock from '../common/LoadingBlock.vue'
import StatusTag from '../common/StatusTag.vue'
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
  },
  canEdit: {
    type: Boolean,
    default: false
  },
  sizeOptions: {
    type: Array,
    default: () => [5, 10, 20, 50]
  }
})

defineEmits(['retry', 'page-change', 'size-change', 'edit'])

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
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
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
  color: var(--color-primary);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.device-table-card h3 {
  margin: 8px 0 0;
  color: var(--color-text-primary);
}

.device-table-card__description,
.device-table-card__page,
.device-table-footer__summary {
  color: var(--color-text-secondary);
}

.device-table-card__meta {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.device-table-shell {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.device-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.device-table th,
.device-table td {
  padding: 16px 18px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
}

.device-table th {
  color: var(--color-text-secondary);
  font-size: 0.92rem;
  font-weight: 700;
  background: var(--color-bg-soft);
}

.device-table tbody tr:hover {
  background: rgba(29, 79, 145, 0.045);
}

.device-table__mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-weight: 700;
}

.device-table__placeholder {
  padding: 44px 24px;
  color: var(--color-text-secondary);
  text-align: center;
}

.table-link {
  color: var(--color-primary);
  font-weight: 700;
}

.table-link:hover,
.table-action-button:hover {
  color: var(--color-primary-hover);
}

.device-table__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.table-action-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.device-table-state {
  margin-top: 0;
}

.device-table-footer__size {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-secondary);
  font-size: 0.92rem;
  font-weight: 650;
}

.device-table-footer__size select {
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
  color: var(--color-text-primary);
  outline: none;
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
