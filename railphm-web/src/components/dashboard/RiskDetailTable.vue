<template>
  <article class="detail-table-card">
    <div class="detail-table-card__header">
      <div>
        <p class="section-tag">结构化结果</p>
        <h3>{{ title }}</h3>
        <p class="section-description">{{ description }}</p>
      </div>

      <span class="detail-table-card__count">{{ rows.length }} 条结果</span>
    </div>

    <div v-if="loading" class="detail-table-card__state">
      <span class="state-skeleton state-skeleton--header"></span>
      <span class="state-skeleton state-skeleton--row"></span>
      <span class="state-skeleton state-skeleton--row"></span>
      <span class="state-skeleton state-skeleton--row"></span>
    </div>

    <div v-else-if="error" class="detail-table-card__state detail-table-card__state--error">
      <h4>结果明细加载失败</h4>
      <p>{{ error }}</p>
    </div>

    <div v-else-if="!rows.length" class="detail-table-card__state">
      <h4>当前暂无可展示的风险结果</h4>
      <p>{{ emptyText }}</p>
    </div>

    <div v-else class="detail-table-card__table-wrap">
      <table class="detail-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.key">{{ column.title }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="`${row.device_id || index}-${row.window_end_time || index}`">
            <td v-for="column in columns" :key="column.key">
              <span
                v-if="row[`${column.key}Tone`]"
                :class="['status-pill', `status-pill--${row[`${column.key}Tone`]}`]"
              >
                {{ row[column.key] }}
              </span>
              <span v-else>{{ row[column.key] }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </article>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '风险结果明细'
  },
  description: {
    type: String,
    default: '展示当前默认设备最新风险结果的结构化字段信息，用于辅助查看模型输出与评估摘要。'
  },
  columns: {
    type: Array,
    default: () => []
  },
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
  emptyText: {
    type: String,
    default: '默认设备尚未返回结果数据。'
  }
})
</script>

<style scoped>
.detail-table-card {
  display: grid;
  gap: 22px;
  padding: 26px 28px;
  background: #ffffff;
  border: 1px solid #d7e1ee;
  border-radius: 22px;
  box-shadow: 0 20px 42px rgba(15, 23, 42, 0.06);
}

.detail-table-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.section-tag,
.section-description {
  margin: 0;
}

.section-tag {
  color: #0f6c85;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-table-card h3,
.detail-table-card h4 {
  margin: 8px 0 0;
  color: #0f172a;
}

.section-description {
  margin-top: 12px;
  color: #5b6d86;
  line-height: 1.7;
}

.detail-table-card__count {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: #f5f8fc;
  border: 1px solid #d7e1ee;
  color: #4a617f;
  font-weight: 600;
}

.detail-table-card__table-wrap {
  overflow-x: auto;
}

.detail-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
}

.detail-table th,
.detail-table td {
  padding: 16px 14px;
  text-align: left;
  border-bottom: 1px solid #e3ebf4;
  white-space: nowrap;
}

.detail-table th {
  color: #52637b;
  background: #f8fbfd;
  font-size: 0.92rem;
  font-weight: 700;
}

.detail-table td {
  color: #17253a;
  font-weight: 500;
}

.detail-table tbody tr:last-child td {
  border-bottom: none;
}

.detail-table-card__state {
  display: grid;
  gap: 12px;
  padding: 24px;
  border-radius: 18px;
  background: #f8fbfd;
  border: 1px dashed #ccd8e6;
  color: #52637b;
}

.detail-table-card__state--error {
  border-style: solid;
  border-color: rgba(220, 38, 38, 0.18);
  background: rgba(254, 242, 242, 0.72);
  color: #991b1b;
}

.detail-table-card__state p {
  margin: 0;
}

.state-skeleton {
  display: inline-flex;
  width: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #edf2f8 0%, #f8fbfd 50%, #edf2f8 100%);
  background-size: 200% 100%;
  animation: table-shimmer 1.4s linear infinite;
}

.state-skeleton--header {
  height: 16px;
  width: 36%;
}

.state-skeleton--row {
  height: 14px;
}

@keyframes table-shimmer {
  from {
    background-position: 200% 0;
  }

  to {
    background-position: -200% 0;
  }
}

@media (max-width: 768px) {
  .detail-table-card {
    padding: 22px;
  }

  .detail-table-card__header {
    flex-direction: column;
  }
}
</style>
