<template>
  <section class="dashboard-page">
    <PageHeader
      title="高铁列控设备健康管理总览"
      eyebrow="系统首页"
      description="集中展示设备运行状态、风险趋势、健康度分布、最新告警和重点关注设备。"
      :meta="headerMetaText"
    >
      <template #actions>
        <span :class="['status-pill', `status-pill--${dashboardStatus.tone}`]">{{ dashboardStatus.label }}</span>
        <span class="status-pill status-pill--default">{{ currentRoleText }}</span>
        <button class="secondary-button" type="button" :disabled="loading" @click="loadDashboard">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </template>
    </PageHeader>

    <ErrorState
      v-if="errorMessage"
      title="Dashboard 数据加载失败"
      :message="errorMessage"
      retry-text="重新加载"
      @retry="loadDashboard"
    />

    <section class="stat-grid dashboard-stat-grid">
      <StatCard
        v-for="item in overviewMetrics"
        :key="item.key"
        :label="item.label"
        :value="item.value"
        :description="item.description"
        :trend="item.trend"
        :type="item.type"
        :loading="loading"
      />
    </section>

    <section class="dashboard-overview-grid">
      <SectionCard
        title="最近风险变化趋势"
        description="按设备运行窗口时间展示最近风险分数，曲线使用 EMA 展示层平滑。"
      >
        <MetricTrendChart
          v-if="loading || errorMessage || riskTrendPoints.length > 0"
          title="风险趋势"
          description="数值越高表示设备风险越高，展示值为 EMA 平滑风险分数。"
          metric-name="风险分数"
          :points="riskTrendPoints"
          :tooltip-details="riskTrendTooltipDetails"
          :loading="loading"
          :error="errorMessage"
          height="340px"
        />
        <EmptyState
          v-else
          title="暂无风险趋势数据"
          description="当前暂无风险趋势数据，请先在风险预测页生成区间风险结果。"
        />
      </SectionCard>

      <SectionCard
        title="健康度分布"
        description="按设备最新健康等级统计正常、关注、预警和告警数量。"
      >
        <LoadingBlock v-if="loading" text="正在加载健康度分布..." height="300px" />
        <EmptyState
          v-else-if="!hasHealthDistribution"
          title="暂无健康度分布数据"
          description="当前暂无设备健康度统计数据。"
        />
        <div v-else class="health-distribution">
          <article
            v-for="item in healthDistributionRows"
            :key="item.key"
            class="health-distribution__row"
          >
            <div class="health-distribution__meta">
              <span>{{ displayText(item.label) }}</span>
              <strong>{{ item.count }}</strong>
            </div>
            <div class="health-distribution__bar" aria-hidden="true">
              <span
                :class="['health-distribution__fill', `health-distribution__fill--${item.level}`]"
                :style="{ width: `${item.percent}%` }"
              ></span>
            </div>
          </article>
        </div>
      </SectionCard>
    </section>

    <section class="dashboard-list-grid">
      <SectionCard
        title="最新告警"
        description="展示最近 5 条真实告警记录。"
      >
        <template #headerActions>
          <RouterLink class="secondary-link" to="/alerts">进入告警中心</RouterLink>
        </template>

        <LoadingBlock v-if="loading" text="正在加载最新告警..." height="260px" />
        <EmptyState
          v-else-if="latestAlerts.length === 0"
          title="暂无告警记录"
          description="当前暂无告警记录。"
        />
        <ul v-else class="dashboard-alert-list">
          <li v-for="item in latestAlerts" :key="item.alert_id || item.alert_time" class="dashboard-alert-item">
            <div class="dashboard-alert-item__header">
              <RiskTag :level="item.alert_level" size="small" />
              <StatusTag
                :value="item.alert_status"
                :label="item.alert_status_text || formatAlertStatus(item.alert_status)"
                :type="getAlertStatusTone(item.alert_status)"
                size="small"
              />
              <span>{{ formatDateTime(getAlertTime(item)) }}</span>
            </div>
            <strong>{{ displayText(getDeviceCode(item)) }} {{ item.device_name ? `/ ${item.device_name}` : '' }}</strong>
            <p>{{ displayText(item.alert_message) }}</p>
            <div class="dashboard-alert-item__metrics">
              <small>风险 {{ formatPercent(item.risk_score, 2) }}</small>
              <small>健康度 {{ formatHealthScore(item.health_score, 2) }}</small>
            </div>
          </li>
        </ul>
      </SectionCard>

      <SectionCard
        title="重点设备"
        description="按最新风险分数筛选最需要关注的设备。"
      >
        <template #headerActions>
          <RouterLink class="secondary-link" to="/devices">进入设备台账</RouterLink>
        </template>

        <LoadingBlock v-if="loading" text="正在加载重点设备..." height="260px" />
        <EmptyState
          v-else-if="keyDevices.length === 0"
          title="暂无重点设备"
          description="当前暂无需要重点关注的设备。"
        />
        <div v-else class="table-shell dashboard-table-shell">
          <table class="status-table dashboard-table">
            <thead>
              <tr>
                <th>设备编号</th>
                <th>设备名称</th>
                <th>状态</th>
                <th>风险分数</th>
                <th>健康度</th>
                <th>告警等级</th>
                <th>窗口时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in keyDevices" :key="item.device_code || item.device_id">
                <td class="dashboard-mono">{{ displayText(getDeviceCode(item)) }}</td>
                <td>{{ displayText(item.device_name) }}</td>
                <td>
                  <StatusTag
                    :value="item.device_status"
                    :label="item.status_text || formatDeviceStatus(item.device_status)"
                    :type="getDeviceStatusTone(item.device_status)"
                    size="small"
                  />
                </td>
                <td class="dashboard-number-cell">{{ formatPercent(item.risk_score, 2) }}</td>
                <td class="dashboard-number-cell">{{ formatHealthScore(item.health_score, 2) }}</td>
                <td>{{ formatNullableAlertLevel(item.alert_level) }}</td>
                <td>{{ formatDateTime(getDeviceWindowTime(item)) }}</td>
                <td>
                  <RouterLink
                    v-if="item.device_id"
                    class="table-link"
                    :to="{ name: 'device-detail', params: { id: item.device_id } }"
                  >
                    查看详情
                  </RouterLink>
                  <span v-else>暂无</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
    </section>

    <SectionCard
      title="快捷入口"
      description="演示路径入口：设备、监测、预测、告警。"
    >
      <div class="quick-link-grid">
        <QuickLinkCard
          v-for="item in DASHBOARD_QUICK_LINKS"
          :key="item.to"
          :item="item"
        />
      </div>
    </SectionCard>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { MetricTrendChart } from '../components/chart'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingBlock from '../components/common/LoadingBlock.vue'
import PageHeader from '../components/common/PageHeader.vue'
import RiskTag from '../components/common/RiskTag.vue'
import SectionCard from '../components/common/SectionCard.vue'
import StatCard from '../components/common/StatCard.vue'
import StatusTag from '../components/common/StatusTag.vue'
import QuickLinkCard from '../components/dashboard/QuickLinkCard.vue'
import { getDashboardOverview } from '../api/dashboard'
import { DASHBOARD_QUICK_LINKS } from '../constants/dashboard'
import { getStoredRole } from '../utils/auth'
import { DISPLAY_SMOOTH_ALPHA, buildRiskHealthCurve } from '../utils/curve'
import {
  displayText,
  formatAlertLevel,
  formatAlertStatus,
  formatDateTime,
  formatDeviceStatus,
  formatHealthScore,
  formatPercent,
  toFiniteNumber
} from '../utils/formatters'

const EMPTY_OVERVIEW = {
  kpi: {
    device_total: 0,
    normal_device_count: 0,
    warning_device_count: 0,
    unhandled_alert_count: 0
  },
  risk_trend: [],
  health_distribution: [],
  latest_alerts: [],
  key_devices: [],
  updated_at: ''
}

const overview = ref({ ...EMPTY_OVERVIEW })
const loading = ref(false)
const errorMessage = ref('')
const now = ref(new Date())
let clockTimer = 0

const currentRoleText = computed(() => {
  const role = getStoredRole()
  return {
    ADMIN: '系统管理员',
    OPS: '运维用户'
  }[role] || '当前用户'
})

const dashboardStatus = computed(() => {
  if (loading.value) {
    return { label: '数据加载中', tone: 'muted' }
  }
  if (errorMessage.value) {
    return { label: '数据待重试', tone: 'warning' }
  }
  return { label: '聚合数据已接入', tone: 'success' }
})

const headerMetaText = computed(() => {
  const currentText = formatDateTime(now.value)
  const updatedText = overview.value.updated_at ? formatDateTime(overview.value.updated_at) : '尚未更新'
  return `当前时间 ${currentText} · 最近更新 ${updatedText}`
})

const kpi = computed(() => overview.value.kpi || EMPTY_OVERVIEW.kpi)

const overviewMetrics = computed(() => [
  {
    key: 'device-total',
    label: '设备总数',
    value: kpi.value.device_total,
    description: '纳入监测的列控设备',
    trend: '设备台账',
    type: 'primary'
  },
  {
    key: 'normal-device',
    label: '正常设备',
    value: kpi.value.normal_device_count,
    description: '当前状态正常',
    trend: '健康运行',
    type: 'success'
  },
  {
    key: 'warning-device',
    label: '预警/告警设备',
    value: kpi.value.warning_device_count,
    description: '需重点关注',
    trend: '状态聚合',
    type: Number(kpi.value.warning_device_count) > 0 ? 'warning' : 'success'
  },
  {
    key: 'unhandled-alert',
    label: '未处理告警',
    value: kpi.value.unhandled_alert_count,
    description: '待运维处理',
    trend: '告警记录',
    type: Number(kpi.value.unhandled_alert_count) > 0 ? 'danger' : 'success'
  }
])

const riskTrend = computed(() => ensureArray(overview.value.risk_trend))
const smoothedRiskTrend = computed(() =>
  buildRiskHealthCurve(riskTrend.value, {
    alpha: DISPLAY_SMOOTH_ALPHA,
    timeGetter: getRiskTrendTime,
    riskGetter: getRiskTrendValue,
    healthGetter: (item) => item.health_score
  })
)
const riskTrendPoints = computed(() =>
  smoothedRiskTrend.value.map((item) => ({
    time: formatTrendTime(item.time),
    value: item.risk_score_smoothed
  }))
)
const riskTrendTooltipDetails = computed(() =>
  smoothedRiskTrend.value.map((item) => [
    { label: '设备编号', value: displayText(getDeviceCode(item)) },
    { label: '风险原始值', value: formatPercent(item.risk_score_raw, 2) },
    { label: '风险平滑值', value: formatPercent(item.risk_score_smoothed, 2) },
    { label: '健康度原始值', value: formatHealthScore(item.health_score_raw, 2) },
    { label: '健康度平滑值', value: formatHealthScore(item.health_score_smoothed, 2) },
    { label: '风险波动', value: formatPercent(item.risk_std, 2) },
    { label: '窗口结束', value: formatDateTime(item.window_end_time || item.time || item.created_at) }
  ])
)

const healthDistribution = computed(() => ensureArray(overview.value.health_distribution))
const healthDistributionTotal = computed(() =>
  healthDistribution.value.reduce((total, item) => total + Number(item.count || 0), 0)
)
const hasHealthDistribution = computed(() => healthDistributionTotal.value > 0)
const healthDistributionRows = computed(() =>
  healthDistribution.value.map((item, index) => ({
    ...item,
    key: `${item.level || item.label || 'level'}-${index}`,
    level: normalizeHealthLevel(item.level || item.health_level || item.health_status),
    label: item.label || formatHealthLevelLabel(item.level || item.health_level || item.health_status),
    percent: healthDistributionTotal.value > 0 ? Math.round((Number(item.count || 0) / healthDistributionTotal.value) * 100) : 0
  }))
)

const latestAlerts = computed(() => ensureArray(overview.value.latest_alerts).slice(0, 5))
const keyDevices = computed(() => ensureArray(overview.value.key_devices))

async function loadDashboard() {
  loading.value = true
  errorMessage.value = ''

  try {
    const result = await getDashboardOverview()
    overview.value = normalizeOverview(result)
  } catch (error) {
    overview.value = { ...EMPTY_OVERVIEW }
    errorMessage.value = error.message || 'Dashboard 数据加载失败，请稍后重试'
  } finally {
    loading.value = false
    now.value = new Date()
  }
}

function normalizeOverview(result) {
  const payload = result?.data && typeof result.data === 'object' ? result.data : result
  const source = payload && typeof payload === 'object' ? payload : {}

  return {
    kpi: {
      ...EMPTY_OVERVIEW.kpi,
      ...(source.kpi || {})
    },
    risk_trend: ensureArray(source.risk_trend),
    health_distribution: ensureArray(source.health_distribution),
    latest_alerts: ensureArray(source.latest_alerts),
    key_devices: ensureArray(source.key_devices),
    updated_at: source.updated_at || ''
  }
}

function ensureArray(value) {
  return Array.isArray(value) ? value : []
}

function formatTrendTime(value) {
  return formatDateTime(value, '暂无').replace(/^(\d{4})-/, '').replace(' ', '\n')
}

function getRiskTrendTime(item) {
  return item?.time || item?.window_end_time || item?.created_at || ''
}

function getRiskTrendValue(item) {
  const riskScore = toFiniteNumber(item?.risk_score)
  if (riskScore !== null) {
    return riskScore
  }

  const averageRiskScore = toFiniteNumber(item?.avg_risk_score)
  if (averageRiskScore !== null) {
    return averageRiskScore
  }

  return toFiniteNumber(item?.max_risk_score)
}

function getDeviceCode(item) {
  return item?.device_code || item?.device_id || ''
}

function getAlertTime(item) {
  return item?.alert_time || item?.created_at || item?.updated_at || ''
}

function getDeviceWindowTime(item) {
  return item?.window_end_time || item?.updated_at || ''
}

function formatNullableAlertLevel(value) {
  return value ? formatAlertLevel(value) : '--'
}

function normalizeHealthLevel(value) {
  const normalizedValue = String(value || '').trim().toLowerCase()
  if (normalizedValue === 'healthy' || normalizedValue === 'good') return 'normal'
  if (normalizedValue === 'critical' || normalizedValue === 'danger' || normalizedValue === 'alert') return 'critical'
  return normalizedValue || 'normal'
}

function formatHealthLevelLabel(value) {
  const normalizedValue = normalizeHealthLevel(value)
  const labelMap = {
    normal: '正常',
    attention: '关注',
    warning: '预警',
    critical: '告警'
  }

  return labelMap[normalizedValue] || displayText(value)
}

function getAlertStatusTone(status) {
  const normalizedStatus = String(status || '').toLowerCase()
  if (normalizedStatus === 'resolved') return 'success'
  if (normalizedStatus === 'processing') return 'info'
  if (normalizedStatus === 'ignored') return 'neutral'
  return 'warning'
}

function getDeviceStatusTone(status) {
  const numericStatus = Number(status)
  if (numericStatus === 1) return 'success'
  if (numericStatus === 2 || numericStatus === 3) return 'warning'
  if (numericStatus === 4) return 'danger'
  return 'neutral'
}

onMounted(() => {
  loadDashboard()
  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 60 * 1000)
})

onBeforeUnmount(() => {
  if (clockTimer) {
    window.clearInterval(clockTimer)
    clockTimer = 0
  }
})
</script>

<style scoped>
.dashboard-page {
  display: grid;
  gap: var(--space-6);
}

.dashboard-stat-grid {
  align-items: stretch;
}

.dashboard-stat-grid :deep(.stat-card) {
  min-height: 178px;
}

.dashboard-stat-grid :deep(.stat-card__label) {
  font-size: var(--font-size-sm);
}

.dashboard-stat-grid :deep(.stat-card__value) {
  font-size: 2.65rem;
  line-height: 1;
}

.dashboard-stat-grid :deep(.stat-card__desc) {
  min-height: auto;
}

.dashboard-overview-grid {
  display: grid;
  gap: var(--space-5);
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.75fr);
  align-items: start;
}

.dashboard-list-grid {
  display: grid;
  gap: var(--space-5);
  grid-template-columns: minmax(340px, 0.82fr) minmax(0, 1.28fr);
  align-items: start;
}

.health-distribution {
  display: grid;
  gap: var(--space-3);
}

.health-distribution__row {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
}

.health-distribution__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.health-distribution__meta span {
  color: var(--color-text-secondary);
  font-weight: 700;
}

.health-distribution__meta strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.health-distribution__bar {
  width: 100%;
  height: 10px;
  overflow: hidden;
  border-radius: var(--radius-pill);
  background: var(--color-neutral-soft);
}

.health-distribution__fill {
  display: block;
  height: 100%;
  min-width: 3px;
  border-radius: inherit;
}

.health-distribution__fill--normal {
  background: var(--color-success);
}

.health-distribution__fill--attention,
.health-distribution__fill--warning {
  background: var(--color-warning);
}

.health-distribution__fill--critical {
  background: var(--color-danger);
}

.health-distribution__fill--danger,
.health-distribution__fill--alert,
.health-distribution__fill--fault {
  background: var(--color-danger);
}

.health-distribution__fill--healthy,
.health-distribution__fill--good {
  background: var(--color-success);
}

.dashboard-table-shell {
  overflow-x: auto;
  border-radius: var(--radius-lg);
}

.dashboard-table {
  min-width: 920px;
}

.dashboard-mono {
  color: var(--color-text-primary);
  font-family: var(--font-family-mono);
  font-weight: 700;
}

.dashboard-number-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.dashboard-alert-list {
  display: grid;
  gap: var(--space-3);
  padding: 0;
  margin: 0;
  list-style: none;
}

.dashboard-alert-item {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, #ffffff 0%, var(--color-bg-soft) 100%);
}

.dashboard-alert-item__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.dashboard-alert-item__header > span:last-child {
  margin-left: auto;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.dashboard-alert-item strong,
.dashboard-alert-item p,
.dashboard-alert-item small {
  margin: 0;
}

.dashboard-alert-item strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-md);
}

.dashboard-alert-item p {
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

.dashboard-alert-item__metrics {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.dashboard-alert-item__metrics small {
  color: var(--color-text-secondary);
  font-weight: 700;
  line-height: var(--line-height-relaxed);
}

.quick-link-grid {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.quick-link-grid :deep(.quick-link-card) {
  min-height: 148px;
}

@media (max-width: 1280px) {
  .quick-link-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .dashboard-overview-grid,
  .dashboard-list-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard-stat-grid :deep(.stat-card__value) {
    font-size: 2.25rem;
  }

  .quick-link-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-alert-item__header > span:last-child {
    margin-left: 0;
  }
}
</style>
