<template>
  <section class="dashboard-page">
    <PageHeader
      title="高铁列控设备健康管理总览"
      eyebrow="系统首页"
      description="集中展示设备当前状态、告警处置情况与健康分布，便于运维人员快速掌握重点设备。"
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
      >
        <template #icon>
          <DashboardIcon :name="item.icon" :tone="item.iconTone || item.type" size="lg" />
        </template>
      </StatCard>
    </section>

    <SectionCard
      title="设备状态总览"
      description="根据活跃告警、最新风险预测和设备台账状态综合判断当前设备状态。"
    >
      <LoadingBlock v-if="loading" text="正在加载设备状态总览..." height="260px" />
      <EmptyState
        v-else-if="deviceStatusCards.length === 0"
        title="暂无设备状态数据"
        description="当前暂无可展示的设备状态卡片。"
      />
      <div v-else class="device-status-grid">
        <article
          v-for="item in deviceStatusCards"
          :key="item.device_id || item.device_code"
          :class="['device-status-card', `device-status-card--${getCurrentStatusLevel(item)}`]"
        >
          <div class="device-status-card__topline" aria-hidden="true"></div>
          <header class="device-status-card__header">
            <div class="device-status-card__identity">
              <DashboardIcon name="device" :tone="getStatusIconTone(item)" size="lg" />
              <div>
                <strong>{{ displayText(item.device_code) }}</strong>
                <span>{{ displayText(item.device_name) }}</span>
              </div>
            </div>
            <span :class="['device-status-badge', `device-status-badge--${getCurrentStatusLevel(item)}`]">
              <span class="device-status-badge__dot" aria-hidden="true"></span>
              {{ displayText(item.current_status_text || formatDeviceStatus(item.current_status)) }}
            </span>
          </header>

          <div class="device-status-card__metrics">
            <div class="device-status-metric">
              <span>当前状态</span>
              <strong>{{ displayText(item.current_status_text || formatDeviceStatus(item.current_status)) }}</strong>
            </div>
            <div class="device-status-metric">
              <span>风险分数</span>
              <strong>{{ formatDeviceRiskScore(item) }}</strong>
            </div>
            <div class="device-status-metric">
              <span>健康度分数</span>
              <strong>{{ formatDeviceHealthScore(item) }}</strong>
            </div>
            <div class="device-status-metric">
              <span>活跃告警</span>
              <strong>{{ formatAlertCount(item.active_alert_count) }}</strong>
            </div>
          </div>

          <div class="device-status-card__details">
            <div>
              <span>状态来源</span>
              <strong>{{ formatStatusSource(item.status_source) }}</strong>
            </div>
            <div>
              <span>最新预测时间</span>
              <strong>{{ formatDateTime(getDevicePredictionTime(item), '--') }}</strong>
            </div>
          </div>

          <p v-if="hasCurrentMessage(item)" class="device-status-card__message">
            {{ displayText(item.current_message, '') }}
          </p>

          <footer class="device-status-card__actions">
            <RouterLink
              v-if="item.device_id"
              :to="{ name: 'device-detail', params: { id: item.device_id } }"
            >
              查看详情
            </RouterLink>
            <span v-else>查看详情</span>
            <RouterLink :to="getAlertRoute(item)">告警记录</RouterLink>
          </footer>
        </article>
      </div>
    </SectionCard>

    <section class="dashboard-support-grid">
      <SectionCard
        title="健康度分布"
        description="按设备当前统一状态统计正常、关注、预警和告警数量。"
      >
        <LoadingBlock v-if="loading" text="正在加载健康度分布..." height="260px" />
        <EmptyState
          v-else-if="healthDistributionRows.length === 0"
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
              <span :class="['health-distribution__dot', `health-distribution__dot--${item.level}`]" aria-hidden="true"></span>
              <span>{{ displayText(item.label) }}</span>
            </div>
            <div class="health-distribution__bar" aria-hidden="true">
              <span
                :class="['health-distribution__fill', `health-distribution__fill--${item.level}`]"
                :style="{ width: `${item.percent}%` }"
              ></span>
            </div>
            <strong class="health-distribution__count">{{ item.count }}</strong>
          </article>
        </div>
      </SectionCard>
      <SectionCard
        title="待处理告警"
        description="展示最近需要运维关注的告警记录。"
      >
        <template #headerActions>
          <RouterLink class="secondary-link" to="/alerts">进入告警中心</RouterLink>
        </template>

        <LoadingBlock v-if="loading" text="正在加载待处理告警..." height="260px" />
        <EmptyState
          v-else-if="pendingAlerts.length === 0"
          title="暂无待处理告警"
          description="当前暂无需要运维处理的告警记录。"
        />
        <ul v-else class="dashboard-alert-list">
          <li v-for="item in pendingAlerts" :key="item.alert_id || item.alert_time" class="dashboard-alert-item">
            <span :class="['alert-level-pill', `alert-level-pill--${getAlertLevelTone(item.alert_level)}`]">
              {{ formatAlertLevelLabel(item.alert_level) }}
            </span>
            <div class="dashboard-alert-item__content">
              <div class="dashboard-alert-item__title">
                <strong>{{ displayText(getDeviceCode(item)) }} / {{ displayText(item.device_name) }}</strong>
                <span>{{ formatDateTime(getAlertTime(item), '--') }}</span>
              </div>
              <p>{{ displayText(item.alert_message) }}</p>
              <StatusTag
                :value="item.alert_status"
                :label="item.alert_status_text || formatAlertStatus(item.alert_status)"
                :type="getAlertStatusTone(item.alert_status)"
                size="small"
              />
            </div>
            <div class="dashboard-alert-item__metrics">
              <small><span>风险</span>{{ formatPercent(item.risk_score, 2, '--') }}</small>
              <small><span>健康度</span>{{ formatHealthScore(item.health_score, 2, '--') }}</small>
            </div>
          </li>
        </ul>
      </SectionCard>
    </section>

    <SectionCard
      title="快捷入口"
      description="常用功能导航。"
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
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import LoadingBlock from '../components/common/LoadingBlock.vue'
import PageHeader from '../components/common/PageHeader.vue'
import SectionCard from '../components/common/SectionCard.vue'
import StatCard from '../components/common/StatCard.vue'
import StatusTag from '../components/common/StatusTag.vue'
import DashboardIcon from '../components/dashboard/DashboardIcon.vue'
import QuickLinkCard from '../components/dashboard/QuickLinkCard.vue'
import { getDashboardOverview } from '../api/dashboard'
import { DASHBOARD_QUICK_LINKS } from '../constants/dashboard'
import { getStoredRole } from '../utils/auth'
import {
  displayText,
  formatAlertStatus,
  formatDateTime,
  formatDeviceStatus,
  formatHealthScore,
  formatPercent
} from '../utils/formatters'

const EMPTY_OVERVIEW = {
  kpi: {
    device_total: 0,
    normal_device_count: 0,
    attention_device_count: 0,
    warning_device_count: 0,
    warning_only_device_count: 0,
    critical_device_count: 0,
    unhandled_alert_count: 0
  },
  device_status_cards: [],
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
  const currentText = formatHeaderTime(now.value)
  const updatedText = overview.value.updated_at ? formatHeaderTime(overview.value.updated_at) : '尚未更新'
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
    type: 'primary',
    icon: 'device',
    iconTone: 'default'
  },
  {
    key: 'normal-device',
    label: '正常设备',
    value: kpi.value.normal_device_count,
    description: '当前状态正常',
    trend: '健康运行',
    type: 'success',
    icon: 'risk'
  },
  {
    key: 'warning-device',
    label: '预警/告警设备',
    value: kpi.value.warning_device_count,
    description: '需重点关注',
    trend: '状态聚合',
    type: Number(kpi.value.warning_device_count) > 0 ? 'warning' : 'success',
    icon: 'alert'
  },
  {
    key: 'unhandled-alert',
    label: '未处理告警',
    value: kpi.value.unhandled_alert_count,
    description: '待运维处理',
    trend: '告警记录',
    type: Number(kpi.value.unhandled_alert_count) > 0 ? 'danger' : 'success',
    icon: 'alert'
  }
])

const deviceStatusCards = computed(() => ensureArray(overview.value.device_status_cards))
const healthDistribution = computed(() => ensureArray(overview.value.health_distribution))
const healthDistributionTotal = computed(() =>
  healthDistribution.value.reduce((total, item) => total + normalizeCount(item.count), 0)
)
const healthDistributionRows = computed(() =>
  healthDistribution.value.map((item, index) => {
    const count = normalizeCount(item.count)
    return {
      ...item,
      key: `${item.level || item.label || 'level'}-${index}`,
      level: normalizeHealthLevel(item.level || item.health_level || item.health_status || item.status),
      label: item.label || formatHealthLevelLabel(item.level || item.health_level || item.health_status || item.status),
      count,
      percent: healthDistributionTotal.value > 0 ? Math.round((count / healthDistributionTotal.value) * 100) : 0
    }
  })
)

const latestAlerts = computed(() => ensureArray(overview.value.latest_alerts))
const pendingAlerts = computed(() =>
  latestAlerts.value.filter((item) => isActiveAlertStatus(item?.alert_status)).slice(0, 5)
)

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
    device_status_cards: ensureArray(source.device_status_cards),
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

function getDeviceCode(item) {
  return item?.device_code || item?.device_id || ''
}

function getAlertTime(item) {
  return item?.alert_time || item?.created_at || item?.updated_at || ''
}

function getDevicePredictionTime(item) {
  return item?.current_event_time || item?.latest_prediction_time || item?.window_end_time || item?.updated_at || ''
}

function getAlertRoute(item) {
  return item?.device_code
    ? { name: 'alerts', query: { device_code: item.device_code } }
    : { name: 'alerts' }
}

function normalizeHealthLevel(value) {
  const normalizedValue = String(value || '').trim().toLowerCase()
  if (normalizedValue === '1') return 'normal'
  if (normalizedValue === '2') return 'attention'
  if (normalizedValue === '3') return 'warning'
  if (normalizedValue === '4') return 'critical'
  if (['normal', 'healthy', 'health', 'good', 'ok', '正常', '健康'].includes(normalizedValue)) return 'normal'
  if (['attention', 'focus', '关注'].includes(normalizedValue)) return 'attention'
  if (['warning', 'warn', 'prewarning', '预警'].includes(normalizedValue)) return 'warning'
  if (['critical', 'danger', 'alert', '告警', '严重', '危险'].includes(normalizedValue)) return 'critical'
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

function isActiveAlertStatus(status) {
  return ['pending', 'unhandled', 'processing'].includes(String(status || '').trim().toLowerCase())
}

function getAlertLevelTone(level) {
  const normalizedLevel = String(level || '').trim().toLowerCase()
  if (normalizedLevel === 'high' || normalizedLevel === 'critical') return 'danger'
  if (normalizedLevel === 'medium' || normalizedLevel === 'warning' || normalizedLevel === 'warn') return 'warning'
  if (normalizedLevel === 'low' || normalizedLevel === 'info') return 'info'
  return 'neutral'
}

function formatAlertLevelLabel(level) {
  const tone = getAlertLevelTone(level)
  if (tone === 'danger') return '高等级告警'
  if (tone === 'warning') return '中等级告警'
  if (tone === 'info') return '低等级告警'
  return '告警记录'
}

function getCurrentStatusLevel(item) {
  const normalizedLevel = normalizeHealthLevel(item?.current_status_level || item?.current_status)
  return ['normal', 'attention', 'warning', 'critical'].includes(normalizedLevel) ? normalizedLevel : 'normal'
}

function getStatusIconTone(item) {
  const level = getCurrentStatusLevel(item)
  if (level === 'normal') return 'success'
  if (level === 'critical') return 'danger'
  return 'warning'
}

function formatStatusSource(value) {
  const sourceMap = {
    active_alert: '活跃告警',
    latest_risk: '最新预测',
    device_status: '台账状态'
  }

  return sourceMap[String(value || '').trim()] || '暂无'
}

function formatAlertCount(value) {
  return `${normalizeCount(value)} 条`
}

function formatDeviceRiskScore(item) {
  return formatPercent(resolveCardMetric(item, 'current_risk_score', 'risk_score'), 2, '--')
}

function formatDeviceHealthScore(item) {
  return formatHealthScore(resolveCardMetric(item, 'current_health_score', 'health_score'), 2, '--')
}

function resolveCardMetric(item, currentKey, fallbackKey) {
  if (hasOwn(item, currentKey)) {
    return item?.[currentKey]
  }

  return item?.[fallbackKey]
}

function hasCurrentMessage(item) {
  return typeof item?.current_message === 'string' && item.current_message.trim() !== ''
}

function hasOwn(item, key) {
  return Object.prototype.hasOwnProperty.call(item || {}, key)
}

function normalizeCount(value) {
  const count = Number(value || 0)
  return Number.isFinite(count) ? count : 0
}

function formatHeaderTime(value) {
  if (value instanceof Date) {
    const pad = (number) => String(number).padStart(2, '0')
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())} ${pad(value.getHours())}:${pad(value.getMinutes())}`
  }

  return formatDateTime(value, '尚未更新').slice(0, 16)
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
  min-height: 148px;
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

.device-status-grid {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.device-status-card {
  --device-status-color: var(--color-success);
  --device-status-soft: var(--color-success-soft);
  --device-status-border: var(--color-success-border);
  position: relative;
  display: grid;
  gap: var(--space-4);
  overflow: hidden;
  padding: var(--space-5);
  border: 1px solid var(--device-status-border);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.05);
}

.device-status-card--attention {
  --device-status-color: #d99a16;
  --device-status-soft: rgba(245, 158, 11, 0.12);
  --device-status-border: rgba(245, 158, 11, 0.34);
}

.device-status-card--warning {
  --device-status-color: #f97316;
  --device-status-soft: rgba(249, 115, 22, 0.12);
  --device-status-border: rgba(249, 115, 22, 0.34);
}

.device-status-card--critical {
  --device-status-color: var(--color-danger);
  --device-status-soft: var(--color-danger-soft);
  --device-status-border: var(--color-danger-border);
}

.device-status-card__topline {
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: var(--device-status-color);
}

.device-status-card__header,
.device-status-card__identity,
.device-status-card__actions,
.device-status-card__details {
  display: flex;
  align-items: center;
}

.device-status-card__header {
  justify-content: space-between;
  gap: var(--space-3);
}

.device-status-card__identity {
  min-width: 0;
  gap: var(--space-3);
}

.device-status-card__identity div {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.device-status-card__identity strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
}

.device-status-card__identity span,
.device-status-metric span,
.device-status-card__details span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.device-status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--device-status-border);
  border-radius: var(--radius-sm);
  background: var(--device-status-soft);
  color: var(--device-status-color);
  font-size: var(--font-size-sm);
  font-weight: 800;
  white-space: nowrap;
}

.device-status-badge__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-pill);
  background: currentColor;
}

.device-status-card__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.device-status-metric {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
  border-right: 1px solid var(--color-border);
}

.device-status-metric:last-child {
  border-right: 0;
}

.device-status-metric strong {
  color: var(--device-status-color);
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
}

.device-status-card__details {
  gap: var(--space-4);
}

.device-status-card__details > div {
  display: grid;
  flex: 1;
  min-width: 0;
  gap: var(--space-2);
  padding: 0 var(--space-4) 0 0;
  border-right: 1px solid var(--color-border);
}

.device-status-card__details > div:last-child {
  border-right: 0;
}

.device-status-card__details strong {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-status-card__message {
  min-height: 24px;
  padding: var(--space-3);
  margin: 0;
  border: 1px solid var(--device-status-border);
  border-radius: var(--radius-md);
  background: var(--device-status-soft);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.device-status-card__actions {
  justify-content: space-around;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.device-status-card__actions a,
.device-status-card__actions span {
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  font-weight: 800;
}

.device-status-card__actions span {
  color: var(--color-text-muted);
}

.dashboard-support-grid {
  display: grid;
  gap: var(--space-5);
  grid-template-columns: minmax(340px, 0.65fr) minmax(0, 1.35fr);
  align-items: stretch;
}

.health-distribution {
  display: grid;
  gap: var(--space-4);
}

.health-distribution__row {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr) 32px;
  gap: var(--space-3);
  align-items: center;
}

.health-distribution__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.health-distribution__meta span {
  color: var(--color-text-secondary);
  font-weight: 700;
}

.health-distribution__count {
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  text-align: right;
}

.health-distribution__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-pill);
  background: var(--color-success);
}

.health-distribution__dot--attention {
  background: #f5b02e;
}

.health-distribution__dot--warning {
  background: #f97316;
}

.health-distribution__dot--critical {
  background: var(--color-danger);
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
  border-radius: inherit;
}

.health-distribution__fill--normal {
  background: var(--color-success);
}

.health-distribution__fill--attention {
  background: #f5b02e;
}

.health-distribution__fill--warning {
  background: #f97316;
}

.health-distribution__fill--critical {
  background: var(--color-danger);
}

.dashboard-alert-list {
  display: grid;
  gap: var(--space-2);
  padding: 0;
  margin: 0;
  list-style: none;
}

.dashboard-alert-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #ffffff;
}

.alert-level-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 var(--space-2);
  border: 1px solid var(--color-neutral-border);
  border-radius: var(--radius-sm);
  background: var(--color-neutral-soft);
  color: var(--color-neutral);
  font-size: var(--font-size-xs);
  font-weight: 800;
  white-space: nowrap;
}

.alert-level-pill--danger {
  border-color: var(--color-danger-border);
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.alert-level-pill--warning {
  border-color: rgba(249, 115, 22, 0.28);
  background: rgba(249, 115, 22, 0.1);
  color: #f97316;
}

.alert-level-pill--info {
  border-color: var(--color-info-border);
  background: var(--color-info-soft);
  color: var(--color-info);
}

.dashboard-alert-item__content {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
}

.dashboard-alert-item__title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.dashboard-alert-item__title strong,
.dashboard-alert-item__title span,
.dashboard-alert-item p {
  margin: 0;
}

.dashboard-alert-item__title strong {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-alert-item__title span {
  flex: none;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.dashboard-alert-item p {
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-alert-item__metrics {
  display: grid;
  gap: var(--space-2);
  min-width: 86px;
  text-align: left;
}

.dashboard-alert-item__metrics small {
  display: grid;
  gap: var(--space-1);
  color: var(--color-danger);
  font-weight: 800;
  line-height: var(--line-height-relaxed);
}

.dashboard-alert-item__metrics small span {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 700;
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
  .device-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quick-link-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .dashboard-support-grid {
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

  .device-status-grid {
    grid-template-columns: 1fr;
  }

  .device-status-card__header,
  .device-status-card__details {
    align-items: flex-start;
    flex-direction: column;
  }

  .device-status-card__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .device-status-metric:nth-child(2n) {
    border-right: 0;
  }

  .device-status-metric:nth-child(-n + 2) {
    border-bottom: 1px solid var(--color-border);
  }

  .device-status-card__details > div {
    width: 100%;
    padding-right: 0;
    border-right: 0;
  }

  .health-distribution__row {
    grid-template-columns: 74px minmax(0, 1fr) 28px;
  }

  .dashboard-alert-item {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .dashboard-alert-item__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .dashboard-alert-item__title {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-1);
  }
}
</style>
