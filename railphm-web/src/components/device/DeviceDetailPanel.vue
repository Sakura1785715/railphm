<template>
  <section class="device-detail-grid">
    <article class="device-detail-hero">
      <div>
        <p class="section-tag">设备档案</p>
        <h3>{{ device.car_no || `设备 ${device.device_id}` }}</h3>
        <p class="device-detail-hero__description">
          当前页面展示设备台账基础信息，并提供运行监测、风险预测和告警中心的业务入口，作为单台 ATP 设备的统一查看起点。
        </p>
      </div>

      <div class="device-detail-hero__meta">
        <span class="device-id-chip">设备 ID {{ device.device_id }}</span>
        <span :class="['status-pill', `status-pill--${statusMeta.tone}`]">{{ statusMeta.label }}</span>
      </div>
    </article>

    <div class="device-detail-summary-grid">
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

      <article class="device-detail-card">
        <div class="device-detail-card__header">
          <div>
            <p class="section-tag">设备状态</p>
            <h3>健康与风险摘要</h3>
          </div>
          <span class="status-pill status-pill--muted">摘要占位</span>
        </div>

        <div class="device-kpi-grid">
          <div class="device-kpi">
            <span>最新健康度</span>
            <strong>待接入</strong>
            <p>后续可复用风险预测接口展示设备健康度。</p>
          </div>
          <div class="device-kpi">
            <span>最新风险</span>
            <strong>待接入</strong>
            <p>保留与风险预测模块联动的摘要区域。</p>
          </div>
          <div class="device-kpi">
            <span>告警摘要</span>
            <strong>待接入</strong>
            <p>后续与告警中心列表筛选条件保持一致。</p>
          </div>
        </div>
      </article>
    </div>

    <article class="device-detail-card">
      <div class="device-detail-card__header">
        <div>
          <p class="section-tag">业务入口</p>
          <h3>围绕该设备继续查看</h3>
        </div>
        <span class="status-pill status-pill--success">入口已保留</span>
      </div>

      <div class="device-detail-action-grid">
        <RouterLink to="/monitor" class="device-detail-action">
          <span class="status-pill status-pill--default">运行监测</span>
          <h3>查看监测曲线</h3>
          <p>进入运行监测模块，后续按设备维度查询 ATP 监测序列。</p>
        </RouterLink>

        <RouterLink to="/predictions" class="device-detail-action">
          <span class="status-pill status-pill--default">风险预测</span>
          <h3>查看风险趋势</h3>
          <p>进入风险预测模块，后续查看该设备历史风险与健康度变化。</p>
        </RouterLink>

        <RouterLink to="/alerts" class="device-detail-action">
          <span class="status-pill status-pill--default">告警中心</span>
          <h3>查看告警记录</h3>
          <p>进入告警中心模块，后续按设备筛选待处理和已处理告警。</p>
        </RouterLink>
      </div>
    </article>

    <article class="device-detail-card device-detail-card--note">
      <p class="section-tag">查看说明</p>
      <h3>当前页面边界</h3>
      <ul class="note-list">
        <li>本次重构不新增编辑、新增或删除设备的业务能力。</li>
        <li>设备详情仍使用既有设备详情接口，字段口径与设备台账列表保持一致。</li>
        <li>运行监测、风险预测和告警中心入口保持原有路由结构，后续可逐步接入真实页面。</li>
      </ul>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
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
.device-detail-grid,
.device-detail-card,
.device-detail-action,
.device-kpi {
  display: grid;
  gap: 20px;
}

.device-detail-summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
  gap: 20px;
}

.device-detail-hero,
.device-detail-card {
  padding: 24px 26px;
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

.device-detail-hero h3,
.device-detail-card h3 {
  margin: 8px 0 0;
}

.device-detail-hero__description {
  margin-top: 12px;
  max-width: 760px;
}

.device-detail-hero__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
  justify-content: flex-end;
}

.device-kpi-grid {
  display: grid;
  gap: 14px;
}

.device-kpi {
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--rail-border);
  background: rgba(255, 255, 255, 0.58);
}

.device-kpi span {
  color: var(--rail-text-muted);
  font-size: 0.9rem;
}

.device-kpi strong {
  color: var(--rail-text-strong);
  font-size: 1.2rem;
}

.device-kpi p {
  margin: 0;
  color: var(--rail-text-muted);
  line-height: 1.7;
}

.note-list {
  padding-left: 20px;
  color: var(--rail-text);
}

.note-list li + li {
  margin-top: 10px;
}

@media (max-width: 1100px) {
  .device-detail-summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .device-detail-hero,
  .device-detail-card__header {
    flex-direction: column;
  }

  .device-detail-hero__meta {
    justify-content: flex-start;
  }
}
</style>