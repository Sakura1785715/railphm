<template>
  <section class="device-detail-grid">
    <article class="device-detail-hero">
      <div>
        <p class="section-tag">设备档案</p>
        <h3>{{ device.car_no || `设备 ${device.device_id}` }}</h3>
        <p class="device-detail-hero__description">
          当前页面展示的是设备台账基础档案信息，可作为后续运行监测、风险预测与告警查看的统一入口。
        </p>
      </div>

      <div class="device-detail-hero__meta">
        <span class="device-id-chip">设备 ID {{ device.device_id }}</span>
        <span :class="['status-pill', `status-pill--${statusMeta.tone}`]">{{ statusMeta.label }}</span>
      </div>
    </article>

    <article class="device-detail-card">
      <div class="device-detail-card__header">
        <div>
          <p class="section-tag">基础信息</p>
          <h3>台账主数据</h3>
        </div>
        <span class="status-pill status-pill--default">{{ device.atp_type || '制式未返回' }}</span>
      </div>

      <dl class="detail-list">
        <div v-for="item in detailItems" :key="item.label">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </div>
      </dl>
    </article>

    <article class="device-detail-card device-detail-card--note">
      <p class="section-tag">查看说明</p>
      <h3>当前页面边界</h3>
      <ul class="note-list">
        <li>仅展示设备台账主数据字段，不扩展编辑、新增或删除操作。</li>
        <li>运行监测、风险预测和告警信息仍保留在各自模块中，避免本页职责膨胀。</li>
        <li>当前详情数据直接来自真实设备详情接口，字段口径与列表保持一致。</li>
      </ul>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { getDeviceStatusMeta } from '../../utils/dashboard'

const props = defineProps({
  device: {
    type: Object,
    required: true
  }
})

const statusMeta = computed(() => getDeviceStatusMeta(props.device.device_status))

const detailItems = computed(() => [
  {
    label: '设备编号',
    value: props.device.device_id ?? '未返回'
  },
  {
    label: '车号',
    value: props.device.car_no || '未返回'
  },
  {
    label: 'ATP 类型',
    value: props.device.atp_type || '未返回'
  },
  {
    label: '配属单位',
    value: props.device.attach_bureau || '未返回'
  },
  {
    label: '设备状态',
    value: statusMeta.value.label
  },
  {
    label: '状态编码',
    value: props.device.device_status ?? '未返回'
  }
])
</script>

<style scoped>
.device-detail-grid {
  display: grid;
  gap: 20px;
}

.device-detail-hero,
.device-detail-card {
  padding: 24px 26px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbfd 100%);
  border: 1px solid #d7e1ee;
  border-radius: 22px;
  box-shadow: 0 20px 42px rgba(15, 23, 42, 0.05);
}

.device-detail-hero,
.device-detail-card__header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.section-tag,
.device-detail-hero__description,
.note-list {
  margin: 0;
}

.section-tag {
  color: #0f6c85;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.device-detail-hero h3,
.device-detail-card h3 {
  margin: 8px 0 0;
  color: #0f172a;
}

.device-detail-hero__description {
  margin-top: 12px;
  max-width: 720px;
  color: #5b6d86;
  line-height: 1.7;
}

.device-detail-hero__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
  justify-content: flex-end;
}

.device-id-chip {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid #d6e2ee;
  background: #f8fbfd;
  color: #45617f;
  font-weight: 600;
}

.detail-list {
  display: grid;
  gap: 16px;
  margin-top: 20px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-list div {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 16px;
  background: rgba(248, 251, 253, 0.92);
  border: 1px solid #e3edf5;
}

.detail-list dt {
  color: #64748b;
  font-size: 0.92rem;
}

.detail-list dd {
  margin: 0;
  color: #0f172a;
  font-size: 1rem;
  font-weight: 700;
}

.device-detail-card--note {
  background: #ffffff;
}

.note-list {
  padding-left: 20px;
  color: #334155;
}

.note-list li + li {
  margin-top: 10px;
}

@media (max-width: 768px) {
  .device-detail-hero,
  .device-detail-card__header {
    flex-direction: column;
  }

  .device-detail-hero,
  .device-detail-card {
    padding: 20px;
  }

  .detail-list {
    grid-template-columns: 1fr;
  }

  .device-detail-hero__meta {
    justify-content: flex-start;
  }
}
</style>
