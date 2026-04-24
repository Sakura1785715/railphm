<template>
  <section class="page-card module-placeholder">
    <div class="page-heading">
      <p class="page-tag">模块预留</p>
      <h2>{{ route.meta.title }}</h2>
      <p class="page-description">
        {{ route.meta.description }}
      </p>
    </div>

    <div class="placeholder-grid">
      <article class="placeholder-card">
        <span class="status-pill status-pill--default">路由已接入</span>
        <h3>页面入口已保留</h3>
        <p>当前模块已经纳入 RailPHM 主导航，后续可在不调整信息架构的前提下继续补全业务页面。</p>
      </article>

      <article class="placeholder-card">
        <span class="status-pill status-pill--muted">接口待联调</span>
        <h3>功能边界清晰</h3>
        <p>保持运行监测、风险预测、告警管理各自独立，避免把多个业务职责混入单一页面。</p>
      </article>

      <article class="placeholder-card">
        <span class="status-pill status-pill--success">视觉已统一</span>
        <h3>遵循设计系统</h3>
        <p>占位状态同样使用统一卡片、标签、按钮和页面节奏，避免系统局部出现简陋断层。</p>
      </article>
    </div>

    <div class="state-panel empty-state">
      当前模块的正式业务能力将在后续任务中继续建设。本页面已作为高质量占位入口保留，适合后续接入图表、列表、筛选和详情区域。
    </div>

    <div class="chart-capability-panel">
      <MetricTrendChart
        title="图表能力已接入"
        description="当前仅用于验证通用图表组件可用，正式业务曲线将在后续任务中替换。"
        metric-name="基础指标"
        unit="%"
        :points="chartPreviewPoints"
        height="260px"
      />
    </div>

    <div class="action-bar">
      <RouterLink to="/" class="primary-link">返回系统首页</RouterLink>
      <RouterLink to="/devices" class="secondary-link">查看设备台账</RouterLink>
      <RouterLink to="/health" class="secondary-link">查看系统联通测试</RouterLink>
    </div>
  </section>
</template>

<script setup>
import { RouterLink, useRoute } from 'vue-router'
import { MetricTrendChart } from '../components/chart'

const route = useRoute()

const chartPreviewPoints = [
  { time: '09:00', value: 72 },
  { time: '10:00', value: 76 },
  { time: '11:00', value: 74 },
  { time: '12:00', value: 79 },
  { time: '13:00', value: 81 }
]
</script>
