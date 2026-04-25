<template>
  <article class="risk-summary-card">
    <div class="risk-summary-card__header">
      <div>
        <p class="section-tag">默认观测设备</p>
        <h3>默认设备最新风险结果</h3>
        <p class="section-description">
          结果来自当前首页默认观测设备的最新一次风险评估，用于辅助研判设备当前健康状态。
        </p>
      </div>

      <div class="risk-summary-card__header-meta">
        <span class="device-chip">设备 ID {{ defaultDeviceId }}</span>
        <button class="link-button" type="button" @click="$emit('retry')" :disabled="loading">
          {{ loading ? '更新中' : '重新获取' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="risk-summary-card__state">
      <span class="state-skeleton state-skeleton--title"></span>
      <span class="state-skeleton state-skeleton--metric"></span>
      <span class="state-skeleton state-skeleton--line"></span>
      <span class="state-skeleton state-skeleton--line state-skeleton--short"></span>
    </div>

    <div v-else-if="error" class="risk-summary-card__state risk-summary-card__state--error">
      <h4>风险结果暂时不可用</h4>
      <p>{{ error }}</p>
      <p class="risk-summary-card__state-hint">首页其他模块仍可正常查看，你可以稍后再次重试。</p>
    </div>

    <div v-else-if="!prediction" class="risk-summary-card__state">
      <h4>当前暂无可展示的风险结果</h4>
      <p>默认设备尚未返回最新评估数据，待后端补充结果后将在此处展示。</p>
    </div>

    <div v-else class="risk-summary-card__content">
      <div class="risk-summary-card__hero">
        <div class="risk-summary-card__device">
          <div class="risk-summary-card__device-title">
            <DashboardIcon name="risk" :tone="riskLevelMeta.tone === 'muted' ? 'accent' : riskLevelMeta.tone" size="lg" />
            <div>
              <p class="section-tag">观测对象</p>
              <h4>{{ deviceTitle }}</h4>
            </div>
          </div>

          <div class="risk-summary-card__chips">
            <span :class="['status-pill', `status-pill--${riskLevelMeta.tone}`]">{{ riskLevelMeta.label }}</span>
            <span :class="['status-pill', `status-pill--${healthStatusMeta.tone}`]">{{ healthStatusMeta.label }}</span>
            <span :class="['status-pill', `status-pill--${deviceStatusMeta.tone}`]">{{ deviceStatusMeta.label }}</span>
          </div>

          <p class="risk-summary-card__hint">{{ riskLevelMeta.description }}</p>
        </div>

        <div class="risk-summary-card__score-grid">
          <div class="score-block">
            <div class="score-block__head">
              <span>风险分数</span>
              <strong>{{ formatDecimal(prediction.risk_score) }}</strong>
            </div>
            <div class="score-block__bar">
              <span class="score-block__fill score-block__fill--risk" :style="{ width: `${riskProgress}%` }"></span>
            </div>
            <p>基于最新时间窗口的风险评分结果</p>
          </div>

          <div class="score-block">
            <div class="score-block__head">
              <span>健康度</span>
              <strong>{{ formatDecimal(prediction.health_score, 1) }}</strong>
            </div>
            <div class="score-block__bar">
              <span class="score-block__fill score-block__fill--health" :style="{ width: `${healthProgress}%` }"></span>
            </div>
            <p>健康度越高说明当前状态越稳定</p>
          </div>
        </div>
      </div>

      <div class="risk-summary-card__meta-grid">
        <div class="meta-item">
          <span>车组编号</span>
          <strong>{{ device?.car_no || '暂无设备详情' }}</strong>
        </div>
        <div class="meta-item">
          <span>风险波动</span>
          <strong>{{ formatDecimal(prediction.risk_std) }}</strong>
        </div>
        <div class="meta-item">
          <span>模型版本</span>
          <strong>{{ prediction.model_version || '未返回' }}</strong>
        </div>
        <div class="meta-item">
          <span>列控制式</span>
          <strong>{{ device?.atp_type || '未返回' }}</strong>
        </div>
        <div class="meta-item">
          <span>所属路局</span>
          <strong>{{ device?.attach_bureau || '未返回' }}</strong>
        </div>
        <div class="meta-item">
          <span>时间窗口</span>
          <strong>{{ formatWindowRange(prediction.window_start_time, prediction.window_end_time) }}</strong>
        </div>
      </div>

      <div class="risk-summary-card__footer">
        <p>结果来自当前时间窗口评估，可用于设备状态研判与后续运维辅助决策。</p>
        <p v-if="deviceError" class="risk-summary-card__footer-hint">设备补充信息加载失败：{{ deviceError }}</p>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import DashboardIcon from './DashboardIcon.vue'
import {
  formatDecimal,
  formatWindowRange,
  getDeviceStatusMeta,
  getHealthStatusMeta,
  getRiskLevelMeta,
  toHealthProgress,
  toRiskProgress
} from '../../utils/dashboard'

defineEmits(['retry'])

const props = defineProps({
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  prediction: {
    type: Object,
    default: null
  },
  device: {
    type: Object,
    default: null
  },
  deviceError: {
    type: String,
    default: ''
  },
  defaultDeviceId: {
    type: Number,
    required: true
  }
})

const riskLevelMeta = computed(() => getRiskLevelMeta(props.prediction?.health_score))
const healthStatusMeta = computed(() => getHealthStatusMeta(props.prediction?.health_score))
const deviceStatusMeta = computed(() => getDeviceStatusMeta(props.device?.device_status))
const riskProgress = computed(() => toRiskProgress(props.prediction?.risk_score))
const healthProgress = computed(() => toHealthProgress(props.prediction?.health_score))

const deviceTitle = computed(() => {
  if (!props.device) {
    return `默认设备 ${props.defaultDeviceId}`
  }

  return `${props.device.car_no} / 设备 ${props.device.device_id}`
})
</script>

<style scoped>
.risk-summary-card {
  display: grid;
  gap: 26px;
  padding: 28px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbfd 100%);
  border: 1px solid #d7e1ee;
  border-radius: 22px;
  box-shadow: 0 24px 50px rgba(15, 23, 42, 0.07);
}

.risk-summary-card__header,
.risk-summary-card__hero,
.score-block__head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.risk-summary-card__header-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-tag,
.section-description,
.risk-summary-card__hint,
.risk-summary-card__footer p {
  margin: 0;
}

.section-tag {
  color: #0f6c85;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.risk-summary-card h3,
.risk-summary-card h4,
.risk-summary-card__state h4 {
  margin: 8px 0 0;
  color: #0f172a;
}

.section-description {
  margin-top: 12px;
  max-width: 720px;
  color: #5b6d86;
  line-height: 1.7;
}

.device-chip {
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

.link-button {
  min-height: 34px;
  padding: 0 14px;
  border: none;
  border-radius: 999px;
  background: rgba(15, 108, 133, 0.08);
  color: #0f6c85;
  cursor: pointer;
  font-weight: 600;
}

.link-button:disabled {
  cursor: wait;
  opacity: 0.7;
}

.risk-summary-card__state {
  display: grid;
  gap: 14px;
  padding: 24px;
  border-radius: 18px;
  background: #f8fbfd;
  border: 1px dashed #ccd8e6;
  color: #52637b;
}

.risk-summary-card__state--error {
  border-style: solid;
  border-color: rgba(220, 38, 38, 0.18);
  background: rgba(254, 242, 242, 0.72);
  color: #991b1b;
}

.risk-summary-card__state p {
  margin: 0;
}

.risk-summary-card__state-hint {
  color: #7f1d1d;
}

.state-skeleton {
  display: inline-flex;
  width: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #edf2f8 0%, #f8fbfd 50%, #edf2f8 100%);
  background-size: 200% 100%;
  animation: summary-shimmer 1.4s linear infinite;
}

.state-skeleton--title {
  height: 18px;
  width: 32%;
}

.state-skeleton--metric {
  height: 64px;
  width: 46%;
}

.state-skeleton--line {
  height: 14px;
}

.state-skeleton--short {
  width: 62%;
}

.risk-summary-card__content {
  display: grid;
  gap: 24px;
}

.risk-summary-card__hero {
  padding: 24px;
  border-radius: 20px;
  background:
    linear-gradient(135deg, rgba(15, 108, 133, 0.06) 0%, rgba(56, 189, 248, 0.02) 100%),
    #ffffff;
  border: 1px solid rgba(170, 191, 212, 0.38);
}

.risk-summary-card__device {
  display: grid;
  gap: 16px;
  align-content: start;
}

.risk-summary-card__device-title {
  display: flex;
  gap: 14px;
  align-items: center;
}

.risk-summary-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.risk-summary-card__hint {
  color: #52637b;
}

.risk-summary-card__score-grid {
  display: grid;
  gap: 16px;
  min-width: min(100%, 360px);
}

.score-block {
  display: grid;
  gap: 10px;
  padding: 18px;
  border-radius: 18px;
  background: rgba(248, 251, 253, 0.9);
  border: 1px solid #dce6f0;
}

.score-block__head span,
.meta-item span,
.score-block p {
  color: #5c6d83;
}

.score-block__head strong,
.meta-item strong {
  color: #0f172a;
}

.score-block__head strong {
  font-size: 1.4rem;
}

.score-block__bar {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #e6edf5;
}

.score-block__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.score-block__fill--risk {
  background: linear-gradient(90deg, #0f6c85 0%, #38bdf8 100%);
}

.score-block__fill--health {
  background: linear-gradient(90deg, #22c55e 0%, #86efac 100%);
}

.score-block p {
  margin: 0;
  font-size: 0.92rem;
}

.risk-summary-card__meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.meta-item {
  display: grid;
  gap: 8px;
  min-height: 108px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid #dbe4ef;
  background: #ffffff;
}

.meta-item strong {
  font-size: 1rem;
  line-height: 1.55;
}

.risk-summary-card__footer {
  display: grid;
  gap: 8px;
  padding-top: 6px;
  color: #52637b;
}

.risk-summary-card__footer-hint {
  color: #9a3412;
}

@keyframes summary-shimmer {
  from {
    background-position: 200% 0;
  }

  to {
    background-position: -200% 0;
  }
}

@media (max-width: 1100px) {
  .risk-summary-card__hero {
    flex-direction: column;
  }

  .risk-summary-card__score-grid {
    min-width: 0;
  }

  .risk-summary-card__meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .risk-summary-card {
    padding: 22px;
  }

  .risk-summary-card__header,
  .risk-summary-card__header-meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .risk-summary-card__meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
