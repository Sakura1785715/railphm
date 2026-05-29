<template>
  <section class="prediction-page">
    <div class="monitor-topbar">
      <div class="monitor-topbar__content">
        <p class="page-tag">风险预测</p>
        <h2>设备故障风险预测</h2>
        <p class="page-description">
          基于 ATP 监测数据执行区间滚动推理，生成风险趋势、健康度趋势，并展示经过抑制后的告警结果。
        </p>
      </div>

      <div class="monitor-topbar__meta">
        <span class="device-chip">当前设备 {{ displayText(rangeInferForm.deviceCode || currentDeviceDisplay) }}</span>
        <span :class="['status-pill', `status-pill--${statusTone}`]">{{ statusLabel }}</span>
        <span class="monitor-topbar__summary">{{ statusDescription }}</span>
      </div>
    </div>

    <section class="prediction-main-grid">
      <aside class="prediction-side-panel prediction-infer-card">
        <div class="monitor-section__header prediction-side-panel__header">
          <div>
            <p class="section-tag">区间滚动推理</p>
            <h3>推理参数</h3>
          </div>
          <p>模型窗口大小固定采用训练参数 30 个连续监测点；本页面仅控制回看范围和区间推理输出步长。</p>
        </div>

        <form class="prediction-infer-form" @submit.prevent="handleRangeInfer">
          <div class="range-infer-grid">
            <label class="filter-field">
              <span>设备编号</span>
              <input
                v-model.trim="rangeInferForm.deviceCode"
                type="text"
                placeholder="ATP001"
                :disabled="rangeInferLoading"
              />
            </label>

            <label class="filter-field">
              <span>预测结束时间</span>
              <input
                v-model.trim="rangeInferForm.endTime"
                type="text"
                placeholder="2026-05-18 10:00:00"
                :disabled="rangeInferLoading"
              />
            </label>

            <label class="filter-field">
              <span>回看时长（分钟）</span>
              <input
                v-model.trim="rangeInferForm.lookbackMinutes"
                type="text"
                placeholder="60"
                :disabled="rangeInferLoading"
              />
            </label>

            <label class="filter-field">
              <span>推理步长（秒）</span>
              <input
                v-model.trim="rangeInferForm.inferenceStrideSeconds"
                type="text"
                placeholder="60"
                :disabled="rangeInferLoading"
              />
            </label>

            <label class="filter-field">
              <span>MC 采样次数</span>
              <input
                v-model.trim="rangeInferForm.mcSamples"
                type="text"
                placeholder="20"
                :disabled="rangeInferLoading"
              />
            </label>

            <div class="range-option-row">
              <div class="filter-field range-checkbox-field">
                <span>保存风险结果</span>
                <label class="checkbox-control">
                  <input v-model="rangeInferForm.persist" type="checkbox" :disabled="rangeInferLoading" />
                  <span>写入风险结果库</span>
                </label>
              </div>

              <div class="filter-field range-checkbox-field">
                <span>生成告警</span>
                <label class="checkbox-control">
                  <input
                    v-model="rangeInferForm.generateAlert"
                    type="checkbox"
                    :disabled="rangeInferLoading || !rangeInferForm.persist"
                  />
                  <span>生成告警</span>
                </label>
              </div>
            </div>

            <p class="field-hint">
              勾选生成告警后，系统会基于区间风险结果生成经过抑制的告警记录。
            </p>
            <p v-if="!rangeInferForm.persist" class="field-hint field-hint--warning">
              生成告警需要保存风险结果，请先勾选保存结果。
            </p>
          </div>

          <div class="action-bar prediction-infer-form__actions">
            <button type="submit" class="primary-button" :disabled="rangeInferLoading">
              {{ rangeInferLoading ? '推理中...' : '生成区间风险曲线' }}
            </button>
          </div>
        </form>

        <div v-if="rangeInferLoading" class="state-panel loading-state">
          正在执行区间滚动推理，请稍候...
        </div>

        <div v-if="rangeInferError" class="state-panel error-state">
          {{ rangeInferError }}
        </div>
      </aside>

      <section class="prediction-infer-card prediction-overview-panel">
        <div class="monitor-section__header">
          <div>
            <p class="section-tag">本次推理概览</p>
            <h3>结论摘要</h3>
          </div>
          <p>{{ rangeInferResult ? '先看结论，再查看曲线、告警和明细。' : '尚未执行区间推理，请填写参数后生成风险曲线。' }}</p>
        </div>

        <div v-if="rangeInferSuccessMessage" class="state-panel success-state range-success-state">
          <span>{{ rangeInferSuccessMessage }}</span>
          <div class="range-success-actions">
            <RouterLink
              class="secondary-button range-success-link"
              :to="{ name: 'alerts', query: { device_code: rangeInferResult?.device_code || rangeInferForm.deviceCode } }"
            >
              查看告警中心
            </RouterLink>
            <RouterLink class="secondary-button range-success-link" :to="{ name: 'home' }">
              刷新 Dashboard
            </RouterLink>
          </div>
        </div>

        <div
          v-if="!rangeInferLoading && !rangeInferError && !rangeInferResult"
          class="state-panel empty-state prediction-empty-hero"
        >
          尚未执行区间推理。输入设备编号和时间范围后，系统将生成本次风险曲线、健康度曲线和告警抑制结果。
        </div>

        <div v-else-if="rangeInferResult" class="prediction-overview-content">
          <article class="prediction-hero-card">
            <div>
              <span>最高风险分数</span>
              <strong>{{ formatPercent(rangeMaxRiskPoint?.risk_score, 2) }}</strong>
              <p>
                发生于 {{ formatDateTime(getRangePointTime(rangeMaxRiskPoint)) }}，
                最新健康度 {{ formatHealthScore(rangeLatestRiskPoint?.health_score, 2) }}。
              </p>
            </div>
            <span :class="['status-pill', `status-pill--${rangeHeroMeta.tone}`]">{{ rangeHeroMeta.label }}</span>
          </article>

          <div class="prediction-summary-grid">
            <article v-for="card in rangeHeroCards" :key="card.key" class="monitor-overview-card">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
            </article>
          </div>

          <div class="prediction-mini-grid">
            <article v-for="card in rangeSecondaryCards" :key="card.key" class="monitor-overview-card">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
            </article>
          </div>

          <div v-if="rangeResultEmptyMessage" class="state-panel empty-state">
            {{ rangeResultEmptyMessage }}
          </div>
        </div>
      </section>
    </section>

    <section class="monitor-section prediction-panel prediction-chart-section">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">趋势图</p>
          <h3>本次风险趋势与健康度趋势</h3>
        </div>
        <p>风险和健康度曲线来自本次区间推理结果，横轴优先使用风险窗口结束时间。</p>
      </div>

      <div v-if="!rangeInferResult" class="state-panel empty-state">
        执行区间推理后，这里会展示本次风险分数和健康度变化。
      </div>

      <div v-else class="range-chart-grid">
        <MetricTrendChart
          title="本次风险趋势"
          description="展示本次区间推理生成的 EMA 平滑风险分数变化。"
          metric-name="风险分数"
          :points="rangeRiskTrendPoints"
          :tooltip-details="rangeRiskTooltipDetails"
          :loading="rangeInferLoading"
          :error="rangeInferError"
          height="330px"
        />

        <MetricTrendChart
          title="本次健康度趋势"
          description="展示风险结果 EMA 平滑映射后的设备健康度变化。"
          metric-name="健康度"
          unit="%"
          :points="rangeHealthTrendPoints"
          :tooltip-details="rangeHealthTooltipDetails"
          :loading="rangeInferLoading"
          :error="rangeInferError"
          height="330px"
        />
      </div>
    </section>

    <section class="monitor-section prediction-panel prediction-alert-section">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">告警结果</p>
          <h3>本次告警概览与抑制详情</h3>
        </div>
        <p>告警判断以后端返回为准；片段合并解释为什么异常点多于最终告警数量。</p>
      </div>

      <div v-if="!rangeInferResult" class="state-panel empty-state">
        执行区间推理后，这里会展示告警统计、生成告警和异常片段抑制原因。
      </div>

      <div v-else class="prediction-alert-content">
        <div class="prediction-alert-summary-grid">
          <article v-for="card in rangeAlertSummaryCards" :key="card.key" class="monitor-overview-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </article>
        </div>

        <div class="range-detail-block range-alert-panel">
          <div class="range-detail-header">
            <div>
              <h4>本次生成告警</h4>
              <p>{{ rangeAlertGenerationMessage }}</p>
            </div>
          </div>

          <div v-if="hasRangeAlerts" class="range-detail-table-wrap">
            <table class="range-detail-table range-alert-table">
              <thead>
                <tr>
                  <th>告警ID</th>
                  <th>设备编号</th>
                  <th>告警等级</th>
                  <th>告警状态</th>
                  <th>风险分数</th>
                  <th>健康度</th>
                  <th>告警时间</th>
                  <th>告警信息</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rangeAlertRows" :key="row.key" :title="displayText(row.alert_advice)">
                  <td>{{ displayText(row.alert_id) }}</td>
                  <td>{{ displayText(row.device_code) }}</td>
                  <td>{{ formatAlertLevel(row.alert_level) }}</td>
                  <td>{{ formatAlertStatus(row.alert_status_text || row.alert_status) }}</td>
                  <td>{{ formatPercent(row.risk_score, 2) }}</td>
                  <td>{{ formatHealthScore(row.health_score, 2) }}</td>
                  <td>{{ formatDateTime(row.alert_time) }}</td>
                  <td class="range-table-message">{{ displayText(row.alert_message) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="state-panel empty-state">
            本次区间推理未生成新的告警记录。
          </div>
        </div>

        <div class="range-detail-block range-alert-panel">
          <div class="range-detail-header">
            <div>
              <h4>异常片段与抑制详情</h4>
              <p>{{ rangeAlertSegmentMessage }}</p>
            </div>
          </div>

          <div v-if="hasRangeAlertSegments" class="range-detail-table-wrap">
            <table class="range-detail-table range-alert-segment-table">
              <thead>
                <tr>
                  <th>告警等级</th>
                  <th>片段时间</th>
                  <th>片段点数</th>
                  <th>最高风险</th>
                  <th>代表点时间</th>
                  <th>是否抑制</th>
                  <th>抑制原因</th>
                  <th>告警ID / 已有告警ID</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rangeAlertSegmentRows" :key="row.key">
                  <td>{{ formatAlertLevel(row.alert_level) }}</td>
                  <td>{{ formatDateTime(row.segment_start_time) }} ~ {{ formatDateTime(row.segment_end_time) }}</td>
                  <td>{{ formatInteger(row.point_count) }}</td>
                  <td>{{ formatPercent(row.max_risk_score, 2) }}</td>
                  <td>{{ formatDateTime(row.representative_time) }}</td>
                  <td>{{ formatSuppressedStatus(row.suppressed) }}</td>
                  <td>{{ formatSuppressReason(row.suppress_reason) }}</td>
                  <td>{{ displayText(row.alert_id || row.existing_alert_id) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="state-panel empty-state">
            {{ rangeAlertSegmentEmptyMessage }}
          </div>
        </div>
      </div>
    </section>

    <section class="monitor-section prediction-panel prediction-detail-section">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">明细</p>
          <h3>推理结果明细</h3>
        </div>
        <p>默认展示前 100 条业务字段，技术字段收纳在高级详情中。</p>
      </div>

      <div v-if="!rangeInferResult" class="state-panel empty-state">
        执行区间推理后，这里会展示风险点明细。
      </div>

      <template v-else>
        <div class="range-detail-block">
          <div class="range-detail-header">
            <div>
              <h4>风险点列表</h4>
              <p v-if="rangeDetailOverflow">当前仅展示前 100 条，完整数据已用于曲线绘制。</p>
            </div>
          </div>

          <div v-if="rangeDetailRows.length" class="range-detail-table-wrap">
            <table class="range-detail-table range-risk-detail-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>风险分数</th>
                  <th>风险标准差</th>
                  <th>健康度</th>
                  <th>健康等级</th>
                  <th>预测标签</th>
                  <th>工况标签</th>
                  <th>窗口开始</th>
                  <th>窗口结束</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rangeDetailRows" :key="row.key">
                  <td>{{ formatDateTime(row.time) }}</td>
                  <td>{{ formatPercent(row.risk_score, 2) }}</td>
                  <td>{{ formatPercent(row.risk_std, 2) }}</td>
                  <td>{{ formatHealthScore(row.health_score, 2) }}</td>
                  <td>{{ displayText(row.health_level || row.health_status) }}</td>
                  <td>{{ displayText(row.predicted_label) }}</td>
                  <td>{{ displayText(row.condition_label) }}</td>
                  <td>{{ formatDateTime(row.window_start_time) }}</td>
                  <td>{{ formatDateTime(row.window_end_time) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="state-panel empty-state">
            当前时间范围内未生成有效风险点，请检查监测数据连续性或调整结束时间。
          </div>
        </div>

        <details class="prediction-advanced-panel">
          <summary>高级详情：模型、校准、不确定性与 trace</summary>
          <div class="prediction-detail-groups">
            <div v-for="group in rangeAdvancedGroups" :key="group.title" class="prediction-detail-group">
              <h4>{{ group.title }}</h4>
              <dl class="prediction-detail-grid">
                <div v-for="field in group.fields" :key="field.key">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ field.value }}</dd>
                </div>
              </dl>
            </div>
          </div>
        </details>
      </template>
    </section>

    <section class="monitor-section prediction-panel prediction-history-section">
      <div class="monitor-section__header">
        <div>
          <p class="section-tag">历史查询</p>
          <h3>历史风险结果查询</h3>
        </div>
        <p>用于查询已持久化风险结果，和本次区间推理结果相互独立。</p>
      </div>

      <form class="monitor-filter-card prediction-history-filter" @submit.prevent="handleSearch">
        <div class="monitor-filter-grid prediction-filter-grid">
          <label class="filter-field">
            <span>设备编号</span>
            <input v-model.trim="filters.deviceId" type="text" placeholder="ATP001" :disabled="queryLoading" />
          </label>

          <label class="filter-field">
            <span>开始时间</span>
            <input
              v-model.trim="filters.startTime"
              type="text"
              placeholder="2026-04-01 08:00:00"
              :disabled="queryLoading"
            />
          </label>

          <label class="filter-field">
            <span>结束时间</span>
            <input
              v-model.trim="filters.endTime"
              type="text"
              placeholder="2026-04-01 11:00:00"
              :disabled="queryLoading"
            />
          </label>
        </div>

        <div class="action-bar monitor-filter-card__actions">
          <button type="submit" class="primary-button" :disabled="queryLoading">
            {{ queryLoading ? '查询中...' : '查询风险结果' }}
          </button>
          <button type="button" class="secondary-button" :disabled="queryLoading" @click="handleReset">
            重置
          </button>
        </div>
      </form>

      <div v-if="validationMessage" class="state-panel error-state">
        {{ validationMessage }}
      </div>

      <div v-if="queryLoading && !hasPredictionData" class="state-panel loading-state">
        正在加载风险预测数据...
      </div>

      <div v-if="queryErrorMessage" class="state-panel error-state">
        风险预测数据加载失败：{{ queryErrorMessage }}
      </div>

      <div v-if="historyEmptyMessage" class="state-panel empty-state">
        {{ historyEmptyMessage }}
      </div>

      <div class="prediction-panel__meta">
        <span class="device-chip">设备编号 {{ currentDeviceDisplay }}</span>
        <span :class="['status-pill', `status-pill--${latestRiskMeta.tone}`]">{{ latestRiskMeta.label }}</span>
        <span v-if="latestRecord" class="latest-compact-text">
          最新风险 {{ formatPercent(latestRecord.risk_score, 2) }}，
          健康度 {{ formatHealthScore(latestRecord.health_score, 2) }}，
          窗口结束 {{ formatDateTime(latestRecord.window_end_time || latestRecord.ts_end) }}
        </span>
        <button
          v-if="latestRecord"
          type="button"
          class="secondary-button compact-toggle-button"
          @click="showLatestCard = !showLatestCard"
        >
          {{ showLatestCard ? '收起最新结果' : '展开最新结果' }}
        </button>
      </div>

      <div
        v-if="!latestRecord && !queryLoading && !queryErrors.latest && hasLoaded"
        class="state-panel empty-state"
      >
        当前设备暂无最新风险结果。
      </div>

      <div
        v-else-if="latestRecord && showLatestCard"
        class="monitor-overview-grid prediction-overview-grid"
      >
        <article class="monitor-overview-card">
          <span>设备编号</span>
          <strong>{{ displayText(latestRecord.device_code || latestRecord.device_id) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>风险分数</span>
          <strong>{{ formatPercent(latestRecord.risk_score, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>健康度</span>
          <strong>{{ formatHealthScore(latestRecord.health_score, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>健康等级</span>
          <strong>{{ displayText(latestRecord.health_level || latestRecord.health_status) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>风险波动</span>
          <strong>{{ formatPercent(latestRecord.risk_std, 2) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>工况标签</span>
          <strong>{{ displayText(latestRecord.condition_label) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>窗口开始时间</span>
          <strong>{{ displayText(latestRecord.window_start_time) }}</strong>
        </article>
        <article class="monitor-overview-card">
          <span>窗口结束时间</span>
          <strong>{{ displayText(latestRecord.window_end_time) }}</strong>
        </article>
      </div>

      <div class="prediction-chart-grid">
        <MetricTrendChart
          title="历史风险趋势"
          description="展示指定设备在查询时间范围内的 EMA 平滑风险分数变化。"
          metric-name="风险分数"
          :points="riskTrendPoints"
          :tooltip-details="historyTooltipDetails"
          :loading="queryLoading"
          :error="queryErrors.healthCurve"
          height="300px"
        />

        <MetricTrendChart
          title="历史健康度趋势"
          description="展示指定设备在查询时间范围内的 EMA 平滑健康度变化。"
          metric-name="健康度"
          unit="%"
          :points="healthTrendPoints"
          :tooltip-details="historyTooltipDetails"
          :loading="queryLoading"
          :error="queryErrors.healthCurve"
          height="300px"
        />
      </div>
    </section>

    <details class="prediction-infer-card prediction-debug-card">
      <summary>高级调试：单点推理</summary>
      <div class="prediction-debug-content">
        <div class="monitor-section__header">
          <div>
            <p class="section-tag">高级调试</p>
            <h3>单点推理调试</h3>
          </div>
          <p>保留原单点推理入口用于调试，本页主流程为区间滚动推理。</p>
        </div>

        <form class="prediction-infer-form" @submit.prevent="handleInfer">
          <div class="prediction-infer-grid">
            <label class="filter-field">
              <span>设备编号</span>
              <input v-model.trim="inferForm.deviceId" type="text" placeholder="ATP001" :disabled="inferLoading" />
            </label>

            <label class="filter-field">
              <span>ts_end</span>
              <input
                v-model.trim="inferForm.tsEnd"
                type="text"
                placeholder="2026-05-18 10:05:00"
                :disabled="inferLoading"
              />
            </label>

            <label class="filter-field">
              <span>window_minutes</span>
              <input
                v-model.trim="inferForm.windowMinutes"
                type="text"
                placeholder="5"
                :disabled="inferLoading"
              />
            </label>
          </div>

          <div class="action-bar prediction-infer-form__actions">
            <button type="submit" class="secondary-button" :disabled="inferLoading">
              {{ inferLoading ? '推理中...' : '触发单点推理' }}
            </button>
          </div>
        </form>

        <div v-if="inferLoading" class="state-panel loading-state">
          正在触发单点风险推理...
        </div>

        <div v-if="inferError" class="state-panel error-state">
          {{ inferError }}
        </div>

        <div v-if="inferResult" class="prediction-infer-result">
          <div class="prediction-panel__meta">
            <span class="device-chip">设备编号 {{ displayText(inferResult.device_code || inferResult.device_id) }}</span>
            <span :class="['status-pill', `status-pill--${inferAlertMeta.tone}`]">{{ inferAlertMeta.label }}</span>
            <span class="status-pill status-pill--default">{{ displayText(inferResult.condition_label) }}</span>
          </div>

          <div class="monitor-overview-grid prediction-overview-grid">
            <article class="monitor-overview-card">
              <span>风险分数</span>
              <strong>{{ formatPercent(inferResult.risk_score, 2) }}</strong>
            </article>
            <article class="monitor-overview-card">
              <span>健康度</span>
              <strong>{{ formatHealthScore(inferResult.health_score, 2) }}</strong>
            </article>
            <article class="monitor-overview-card">
              <span>健康等级</span>
              <strong>{{ displayText(inferResult.health_level || inferResult.health_status) }}</strong>
            </article>
            <article class="monitor-overview-card">
              <span>风险波动</span>
              <strong>{{ formatPercent(inferResult.risk_std, 2) }}</strong>
            </article>
          </div>

          <div class="prediction-detail-groups">
            <div v-for="group in inferDetailGroups" :key="group.title" class="prediction-detail-group">
              <h4>{{ group.title }}</h4>
              <dl class="prediction-detail-grid">
                <div v-for="field in group.fields" :key="field.key">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ field.value }}</dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { MetricTrendChart } from '../components/chart'
import {
  getHealthCurve,
  getLatestPrediction,
  getPredictionHistory,
  inferPrediction,
  inferPredictionRange
} from '../api/prediction'
import { getRiskLevelMeta } from '../utils/dashboard'
import {
  displayText,
  formatAlertLevel,
  formatAlertStatus,
  formatBoolean,
  formatCalibrationMethod,
  formatDataSource,
  formatDateTime,
  formatHealthScore,
  formatPercent,
  formatUncertaintyMethod,
  toFiniteNumber
} from '../utils/formatters'
import { DISPLAY_SMOOTH_ALPHA, buildRiskHealthCurve } from '../utils/curve'

const route = useRoute()

const DEFAULT_FILTERS = {
  deviceId: 'ATP001',
  startTime: '2026-05-18 10:00:00',
  endTime: '2026-05-18 10:10:00'
}

const DEFAULT_INFER_FORM = {
  deviceId: DEFAULT_FILTERS.deviceId,
  tsEnd: '2026-05-18 10:05:00',
  windowMinutes: '5'
}

const DEFAULT_RANGE_INFER_FORM = {
  deviceCode: DEFAULT_FILTERS.deviceId,
  endTime: '2026-05-18 10:00:00',
  lookbackMinutes: '60',
  inferenceStrideSeconds: '60',
  mcSamples: '20',
  persist: true,
  generateAlert: true
}
const queryDeviceId = normalizeQueryDeviceId(route.query.device_code || route.query.device_id)
const filters = reactive({
  ...DEFAULT_FILTERS,
  deviceId: queryDeviceId || DEFAULT_FILTERS.deviceId
})
const inferForm = reactive({
  ...DEFAULT_INFER_FORM,
  deviceId: filters.deviceId
})
const rangeInferForm = reactive({
  ...DEFAULT_RANGE_INFER_FORM,
  deviceCode: filters.deviceId
})

const queryLoading = ref(false)
const validationMessage = ref('')
const hasLoaded = ref(false)
const showLatestCard = ref(false)
const latestRecord = ref(null)
const historyRecords = ref([])
const healthCurveRecords = ref([])
const historyMeta = ref({
  device_id: DEFAULT_FILTERS.deviceId,
  start_time: DEFAULT_FILTERS.startTime,
  end_time: DEFAULT_FILTERS.endTime
})
const queryErrors = reactive({
  latest: '',
  history: '',
  healthCurve: ''
})

const inferLoading = ref(false)
const inferError = ref('')
const inferResult = ref(null)
const rangeInferLoading = ref(false)
const rangeInferError = ref('')
const rangeInferResult = ref(null)

const hasPredictionData = computed(
  () => Boolean(latestRecord.value) || historyRecords.value.length > 0 || healthCurveRecords.value.length > 0
)
const latestRiskMeta = computed(() => getRiskLevelMeta(latestRecord.value?.health_score))
const currentDeviceDisplay = computed(
  () => displayText(latestRecord.value?.device_code || latestRecord.value?.device_id || historyMeta.value.device_id || filters.deviceId)
)

const queryErrorMessage = computed(() =>
  [
    queryErrors.latest ? `最新结果：${queryErrors.latest}` : '',
    queryErrors.history ? `历史趋势：${queryErrors.history}` : '',
    queryErrors.healthCurve ? `健康度曲线：${queryErrors.healthCurve}` : ''
  ]
    .filter(Boolean)
    .join('；')
)

const historyEmptyMessage = computed(() => {
  if (!hasLoaded.value || queryLoading.value || queryErrors.history || queryErrors.healthCurve) {
    return ''
  }

  return historyRecords.value.length === 0 && healthCurveRecords.value.length === 0
    ? '当前时间范围内暂无健康度曲线数据。'
    : ''
})

const riskTrendPoints = computed(() =>
  healthCurveRecords.value.map((item) => ({
    time: getRecordTime(item),
    value: item.risk_score_smoothed
  }))
)

const healthTrendPoints = computed(() =>
  healthCurveRecords.value.map((item) => ({
    time: getRecordTime(item),
    value: item.health_score_smoothed
  }))
)

const historyTooltipDetails = computed(() =>
  healthCurveRecords.value.map((item) => [
    { label: '风险原始值', value: formatPercent(item.risk_score_raw, 2) },
    { label: '风险平滑值', value: formatPercent(item.risk_score_smoothed, 2) },
    { label: '健康度原始值', value: formatHealthScore(item.health_score_raw, 2) },
    { label: '健康度平滑值', value: formatHealthScore(item.health_score_smoothed, 2) },
    { label: '风险波动', value: formatPercent(item.risk_std, 2) },
    { label: '健康等级', value: displayText(item.health_level || item.health_status) },
    { label: '工况标签', value: displayText(item.condition_label) },
    { label: '模型版本', value: displayText(item.model_version) }
  ])
)

const rangeRiskSeries = computed(() =>
  Array.isArray(rangeInferResult.value?.risk_series) ? rangeInferResult.value.risk_series : []
)

const rangeSkippedWindows = computed(() =>
  Array.isArray(rangeInferResult.value?.skipped_windows) ? rangeInferResult.value.skipped_windows : []
)

const rangeAlerts = computed(() =>
  Array.isArray(rangeInferResult.value?.alerts) ? rangeInferResult.value.alerts : []
)

const rangeAlertSegments = computed(() =>
  Array.isArray(rangeInferResult.value?.alert_segments) ? rangeInferResult.value.alert_segments : []
)

const smoothedRangeRiskSeries = computed(() =>
  buildRiskHealthCurve(rangeRiskSeries.value, {
    alpha: DISPLAY_SMOOTH_ALPHA,
    timeGetter: getRangePointTime,
    riskGetter: (item) => item.risk_score,
    healthGetter: (item) => item.health_score
  })
)

const rangeRiskTrendPoints = computed(() =>
  smoothedRangeRiskSeries.value.map((item) => ({
    time: getRangePointTime(item),
    value: item.risk_score_smoothed
  }))
)

const rangeHealthTrendPoints = computed(() =>
  smoothedRangeRiskSeries.value.map((item) => ({
    time: getRangePointTime(item),
    value: item.health_score_smoothed
  }))
)

const rangeRiskTooltipDetails = computed(() =>
  smoothedRangeRiskSeries.value.map((item) => [
    { label: '风险原始值', value: formatPercent(item.risk_score_raw, 2) },
    { label: '风险平滑值', value: formatPercent(item.risk_score_smoothed, 2) },
    { label: '健康度原始值', value: formatHealthScore(item.health_score_raw, 2) },
    { label: '健康度平滑值', value: formatHealthScore(item.health_score_smoothed, 2) },
    { label: '风险标准差', value: formatPercent(item.risk_std, 2) },
    { label: '阈值', value: formatPercent(item.threshold, 2) },
    { label: '工况标签', value: displayText(item.condition_label) }
  ])
)

const rangeHealthTooltipDetails = computed(() => {
  const riskByTime = new Map(smoothedRangeRiskSeries.value.map((item) => [getRangePointTime(item), item]))

  return rangeHealthTrendPoints.value.map((point) => {
    const riskItem = riskByTime.get(point.time)
    return [
      { label: '健康等级', value: displayText(riskItem?.health_level || riskItem?.health_status) },
      { label: '风险原始值', value: formatPercent(riskItem?.risk_score_raw, 2) },
      { label: '风险平滑值', value: formatPercent(riskItem?.risk_score_smoothed, 2) },
      { label: '健康度原始值', value: formatHealthScore(riskItem?.health_score_raw, 2) },
      { label: '健康度平滑值', value: formatHealthScore(riskItem?.health_score_smoothed, 2) },
      { label: '窗口结束', value: formatDateTime(riskItem?.window_end_time || point.time) }
    ]
  })
})

const rangeMaxRiskPoint = computed(() => {
  if (!rangeRiskSeries.value.length) {
    return null
  }

  return rangeRiskSeries.value.reduce((maxPoint, item) => {
    const currentRisk = toFiniteNumber(item.risk_score)
    const maxRisk = toFiniteNumber(maxPoint?.risk_score)
    if (maxRisk === null) {
      return item
    }
    if (currentRisk === null) {
      return maxPoint
    }
    return currentRisk >= maxRisk ? item : maxPoint
  }, null)
})

const rangeLatestRiskPoint = computed(() =>
  rangeRiskSeries.value.length ? rangeRiskSeries.value[rangeRiskSeries.value.length - 1] : null
)

const rangeAverageHealthScore = computed(() => {
  const values = rangeHealthTrendPoints.value
    .map((item) => toFiniteNumber(item.value))
    .filter((value) => value !== null)
  if (!values.length) {
    return null
  }

  return values.reduce((total, value) => total + value, 0) / values.length
})

const rangeHeroMeta = computed(() => {
  if (!rangeInferResult.value) {
    return {
      label: '等待区间推理',
      tone: 'default'
    }
  }

  if (toFiniteNumber(rangeInferResult.value.alert_count) > 0) {
    return {
      label: '已生成告警',
      tone: 'danger'
    }
  }

  if (toFiniteNumber(rangeInferResult.value.alert_segment_count) > 0) {
    return {
      label: '异常已抑制',
      tone: 'warning'
    }
  }

  return {
    label: '未触发告警',
    tone: 'success'
  }
})

const rangeHeroCards = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return []
  }

  return [
    { key: 'latest-health', label: '最新健康度', value: formatHealthScore(rangeLatestRiskPoint.value?.health_score, 2) },
    { key: 'avg-health', label: '平均健康度', value: formatHealthScore(rangeAverageHealthScore.value, 2) },
    { key: 'result-count', label: '生成风险点', value: formatInteger(result.result_count) },
    { key: 'alert-count', label: '生成告警', value: formatInteger(result.alert_count) }
  ]
})

const rangeSecondaryCards = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return []
  }

  return [
    { key: 'saved-count', label: '保存结果', value: formatInteger(result.saved_count) },
    { key: 'skipped-existing', label: '重复跳过', value: formatInteger(result.skipped_existing_count) },
    { key: 'skipped-window', label: '数据不足跳过', value: formatInteger(result.skipped_window_count) },
    { key: 'alert-segments', label: '异常片段', value: formatInteger(result.alert_segment_count) },
    { key: 'suppressed-alerts', label: '抑制异常点', value: formatInteger(result.suppressed_alert_count) },
    { key: 'suppress-window', label: '告警抑制窗口', value: formatMinutes(result.alert_suppress_window_minutes) }
  ]
})

const rangeDetailRows = computed(() => rangeRiskSeries.value.slice(0, 100))
const rangeDetailOverflow = computed(() => rangeRiskSeries.value.length > 100)
const rangeSkippedPreview = computed(() => rangeSkippedWindows.value.slice(0, 5))
const rangeAlertRows = computed(() => rangeAlerts.value.map((item, index) => normalizeRangeAlert(item, index)))
const rangeAlertSegmentRows = computed(() =>
  rangeAlertSegments.value.map((item, index) => normalizeRangeAlertSegment(item, index))
)
const hasRangeAlerts = computed(() => rangeAlertRows.value.length > 0)
const hasRangeAlertSegments = computed(() => rangeAlertSegmentRows.value.length > 0)

const rangeAlertSummaryCards = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return []
  }

  return [
    { key: 'generation-status', label: '告警生成状态', value: rangeAlertGenerationStatus.value },
    { key: 'suppress-window', label: '告警抑制窗口', value: formatMinutes(result.alert_suppress_window_minutes) },
    { key: 'segment-count', label: '异常片段数', value: formatInteger(result.alert_segment_count) },
    { key: 'alert-count', label: '生成告警数', value: formatInteger(result.alert_count) },
    { key: 'existing-alert-count', label: '已有告警命中数', value: formatInteger(result.existing_alert_count) },
    { key: 'suppressed-alert-count', label: '抑制异常点数', value: formatInteger(result.suppressed_alert_count) }
  ]
})

const rangeResultEmptyMessage = computed(() => {
  if (!rangeInferResult.value || rangeInferLoading.value || rangeInferError.value) {
    return ''
  }

  return rangeRiskSeries.value.length === 0
    ? '当前时间范围内未生成有效风险点，请检查监测数据连续性或调整结束时间。'
    : ''
})

const rangeAlertGenerationStatus = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return displayText(null)
  }

  if (result.alert_generation_skipped === false) {
    return '告警生成已执行'
  }

  const reason = result.alert_generation_skip_reason
  if (reason === 'generate_alert_false') {
    return '本次未启用告警生成'
  }
  if (reason === 'persist_false') {
    return '本次未生成告警：未保存风险结果'
  }

  return reason ? `本次未生成告警：${reason}` : '本次未生成告警'
})

const rangeAlertGenerationMessage = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return ''
  }

  if (result.alert_generation_skipped) {
    return rangeAlertGenerationStatus.value
  }

  return `本次识别异常片段 ${formatInteger(result.alert_segment_count)} 个，生成告警 ${formatInteger(result.alert_count)} 条，抑制异常点 ${formatInteger(result.suppressed_alert_count)} 个。`
})

const rangeAlertSegmentMessage = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return ''
  }

  if (hasRangeAlertSegments.value) {
    return `告警抑制窗口 ${formatMinutes(result.alert_suppress_window_minutes)}，用于解释风险曲线上多个异常点为何合并为少量告警。`
  }

  return rangeAlertSegmentEmptyMessage.value
})

const rangeAlertSegmentEmptyMessage = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return '本次区间推理未识别到需要告警的异常片段。'
  }

  if (toFiniteNumber(result.result_count) > 0 && toFiniteNumber(result.alert_segment_count) === 0) {
    return '本次风险点未达到告警触发条件。'
  }

  if (toFiniteNumber(result.alert_segment_count) > 0 && toFiniteNumber(result.alert_count) === 0) {
    return '本次识别到异常片段，但由于抑制规则或缺少风险结果ID，未新增告警。'
  }

  return '本次区间推理未识别到需要告警的异常片段。'
})

const rangeInferSuccessMessage = computed(() => {
  const result = rangeInferResult.value
  if (!result || rangeInferLoading.value || rangeInferError.value) {
    return ''
  }

  const baseMessage = `本次区间推理完成，共生成 ${formatInteger(result.result_count)} 个风险点，保存 ${formatInteger(result.saved_count)} 个，重复跳过 ${formatInteger(result.skipped_existing_count)} 个。`
  if (result.alert_generation_skipped) {
    return `${baseMessage}${rangeAlertGenerationStatus.value}。`
  }

  return `${baseMessage}本次识别异常片段 ${formatInteger(result.alert_segment_count)} 个，生成告警 ${formatInteger(result.alert_count)} 条，抑制异常点 ${formatInteger(result.suppressed_alert_count)} 个。`
})

const rangeAdvancedGroups = computed(() => {
  const result = rangeInferResult.value
  if (!result) {
    return []
  }

  const firstPoint = rangeRiskSeries.value[0] || {}
  const latestPoint = rangeLatestRiskPoint.value || {}

  return [
    {
      title: '模型与推理',
      fields: [
        { key: 'model_name', label: '模型名称', value: displayText(result.model_name) },
        { key: 'model_version', label: '模型版本', value: displayText(result.model_version) },
        { key: 'mc_samples', label: 'MC 采样次数', value: displayText(result.mc_samples) },
        { key: 'uncertainty_method', label: '不确定性方法', value: formatUncertaintyMethod(result.uncertainty_method) },
        { key: 'calibration_method', label: '校准方法', value: formatCalibrationMethod(result.calibration_method) },
        { key: 'calibration_enabled', label: '启用校准', value: formatBoolean(result.calibration_enabled) }
      ]
    },
    {
      title: '区间与落库',
      fields: [
        { key: 'device_code', label: '设备编号', value: displayText(result.device_code) },
        { key: 'start_time', label: '区间开始', value: formatDateTime(result.start_time) },
        { key: 'end_time', label: '区间结束', value: formatDateTime(result.end_time) },
        { key: 'monitor_point_count', label: '监测点数', value: formatInteger(result.monitor_point_count) },
        { key: 'first_risk_result_id', label: '首个风险结果ID', value: displayText(firstPoint.risk_result_id) },
        { key: 'latest_risk_result_id', label: '最新风险结果ID', value: displayText(latestPoint.risk_result_id) }
      ]
    },
    {
      title: '跳过窗口',
      fields: [
        { key: 'skipped_window_count', label: '数据不足跳过', value: formatInteger(result.skipped_window_count) },
        { key: 'skipped_preview_1', label: '跳过示例 1', value: formatSkippedWindow(rangeSkippedPreview.value[0]) },
        { key: 'skipped_preview_2', label: '跳过示例 2', value: formatSkippedWindow(rangeSkippedPreview.value[1]) },
        { key: 'skipped_preview_3', label: '跳过示例 3', value: formatSkippedWindow(rangeSkippedPreview.value[2]) }
      ]
    }
  ]
})

const statusTone = computed(() => {
  if (rangeInferLoading.value || queryLoading.value) {
    return 'muted'
  }

  if (rangeInferError.value || validationMessage.value || queryErrors.latest || queryErrors.history || queryErrors.healthCurve) {
    return 'warning'
  }

  if (rangeInferResult.value || hasPredictionData.value) {
    return 'success'
  }

  return 'default'
})

const statusLabel = computed(() => {
  if (rangeInferLoading.value) {
    return '区间推理中'
  }

  if (queryLoading.value) {
    return '历史数据加载中'
  }

  if (rangeInferError.value || validationMessage.value || queryErrors.latest || queryErrors.history || queryErrors.healthCurve) {
    return '查询待处理'
  }

  if (rangeInferResult.value) {
    return '区间推理已完成'
  }

  return '等待区间推理'
})

const statusDescription = computed(() => {
  if (rangeInferLoading.value) {
    return '正在生成本次风险曲线、健康度曲线和告警抑制结果'
  }

  if (rangeInferResult.value) {
    return `最近一次生成 ${formatInteger(rangeInferResult.value.result_count)} 个风险点，告警 ${formatInteger(rangeInferResult.value.alert_count)} 条`
  }

  if (queryLoading.value) {
    return '正在请求历史风险结果'
  }

  if (queryErrors.latest || queryErrors.history || queryErrors.healthCurve) {
    return '部分接口请求失败，可检查后端与 AI 服务状态后重试'
  }

  if (validationMessage.value) {
    return '请补齐设备编号与时间范围'
  }

  return '等待区间推理'
})

const inferAlertMeta = computed(() => {
  const alertLevel = String(inferResult.value?.alert_level || '').toLowerCase()

  if (alertLevel === 'high' || alertLevel === 'critical') {
    return {
      label: formatAlertLevel(alertLevel),
      tone: 'danger'
    }
  }

  if (alertLevel === 'medium' || alertLevel === 'warning') {
    return {
      label: formatAlertLevel(alertLevel),
      tone: 'warning'
    }
  }

  if (alertLevel === 'low' || alertLevel === 'info') {
    return {
      label: formatAlertLevel(alertLevel),
      tone: 'success'
    }
  }

  return {
    label: '结果待解释',
    tone: 'default'
  }
})

const inferDetailGroups = computed(() => {
  const record = inferResult.value
  if (!record) {
    return []
  }

  return [
    {
      title: '结果详情',
      fields: [
        { key: 'risk_result_id', label: '风险结果ID', value: displayText(record.risk_result_id) },
        { key: 'sample_index', label: '样本索引', value: displayText(record.sample_index) },
        { key: 'risk_raw', label: '原始风险', value: formatPercent(record.risk_raw, 2) },
        { key: 'risk_raw_std', label: '原始风险波动', value: formatPercent(record.risk_raw_std, 2) },
        { key: 'threshold', label: '阈值', value: formatPercent(record.threshold, 2) },
        { key: 'predicted_label', label: '预测标签', value: displayText(record.predicted_label) }
      ]
    },
    {
      title: '模型与数据',
      fields: [
        { key: 'model_name', label: '模型名称', value: displayText(record.model_name) },
        { key: 'model_version', label: '模型版本', value: displayText(record.model_version) },
        { key: 'data_source', label: '数据来源', value: formatDataSource(record.data_source) },
        { key: 'condition_label', label: '工况标签', value: displayText(record.condition_label) }
      ]
    },
    {
      title: '校准与不确定性',
      fields: [
        { key: 'calibration_enabled', label: '启用校准', value: formatBoolean(record.calibration_enabled) },
        { key: 'calibration_method', label: '校准方法', value: formatCalibrationMethod(record.calibration_method) },
        { key: 'uncertainty_enabled', label: '启用不确定性', value: formatBoolean(record.uncertainty_enabled) },
        { key: 'uncertainty_method', label: '不确定性方法', value: formatUncertaintyMethod(record.uncertainty_method) },
        { key: 'mc_samples', label: 'MC 样本数', value: displayText(record.mc_samples) },
        { key: 'risk_std', label: '风险标准差', value: formatPercent(record.risk_std, 2) }
      ]
    },
    {
      title: '时间窗口',
      fields: [
        { key: 'window_start_time', label: '窗口开始时间', value: formatDateTime(record.window_start_time) },
        { key: 'window_end_time', label: '窗口结束时间', value: formatDateTime(record.window_end_time) },
        { key: 'ts_end', label: 'ts_end', value: formatDateTime(record.ts_end) },
        { key: 'window_minutes', label: '窗口分钟数', value: displayText(record.window_minutes) }
      ]
    }
  ]
})

watch(
  () => filters.deviceId,
  (deviceId) => {
    inferForm.deviceId = deviceId || DEFAULT_FILTERS.deviceId
    rangeInferForm.deviceCode = deviceId || DEFAULT_FILTERS.deviceId
  }
)

watch(
  () => rangeInferForm.persist,
  (persist) => {
    if (!persist) {
      rangeInferForm.generateAlert = false
    }
  }
)

onMounted(() => {
  fetchPredictionData()
})

async function fetchPredictionData() {
  const message = validateFilters()

  if (message) {
    validationMessage.value = message
    latestRecord.value = null
    historyRecords.value = []
    healthCurveRecords.value = []
    queryErrors.latest = ''
    queryErrors.history = ''
    queryErrors.healthCurve = ''
    return
  }

  queryLoading.value = true
  validationMessage.value = ''
  queryErrors.latest = ''
  queryErrors.history = ''
  queryErrors.healthCurve = ''

  const params = buildQueryParams()
  historyMeta.value = {
    device_id: params.device_id,
    start_time: params.start_time,
    end_time: params.end_time
  }

  try {
    const [latestResult, historyResult, healthCurveResult] = await Promise.allSettled([
      getLatestPrediction({ device_id: params.device_id }),
      getPredictionHistory(params),
      getHealthCurve({ ...params, alpha: DISPLAY_SMOOTH_ALPHA })
    ])

    if (latestResult.status === 'fulfilled') {
      latestRecord.value = normalizeLatest(normalizePayload(latestResult.value))
    } else {
      latestRecord.value = null
      queryErrors.latest = latestResult.reason?.message || '最新风险结果加载失败'
    }

    if (historyResult.status === 'fulfilled') {
      const payload = normalizePayload(historyResult.value)

      historyMeta.value = {
        device_id: payload?.device_id ?? params.device_id,
        start_time: payload?.start_time || params.start_time,
        end_time: payload?.end_time || params.end_time
      }
      historyRecords.value = normalizeHistory(payload)
    } else {
      historyRecords.value = []
      queryErrors.history = historyResult.reason?.message || '历史趋势加载失败'
    }

    if (healthCurveResult.status === 'fulfilled') {
      const payload = normalizePayload(healthCurveResult.value)
      healthCurveRecords.value = normalizeHealthCurve(payload)
    } else {
      healthCurveRecords.value = []
      queryErrors.healthCurve = healthCurveResult.reason?.message || '健康度曲线加载失败'
    }
  } finally {
    hasLoaded.value = true
    queryLoading.value = false
  }
}

async function handleSearch() {
  await fetchPredictionData()
}

async function handleReset() {
  Object.assign(filters, DEFAULT_FILTERS)
  Object.assign(inferForm, DEFAULT_INFER_FORM)
  Object.assign(rangeInferForm, DEFAULT_RANGE_INFER_FORM)
  inferError.value = ''
  inferResult.value = null
  rangeInferError.value = ''
  rangeInferResult.value = null
  await fetchPredictionData()
}

async function handleRangeInfer() {
  const message = validateRangeInferForm()

  if (message) {
    rangeInferError.value = message
    rangeInferResult.value = null
    return
  }

  rangeInferLoading.value = true
  rangeInferError.value = ''
  rangeInferResult.value = null

  try {
    const result = await inferPredictionRange(buildRangeInferPayload())
    rangeInferResult.value = normalizeRangeInferResult(normalizePayload(result))

    if (rangeInferForm.persist) {
      filters.deviceId = rangeInferResult.value?.device_code || rangeInferForm.deviceCode
      filters.startTime = rangeInferResult.value?.start_time || filters.startTime
      filters.endTime = rangeInferResult.value?.end_time || filters.endTime
      await fetchPredictionData()
    }
  } catch (error) {
    rangeInferError.value = error.message || '区间滚动推理失败，请稍后重试'
  } finally {
    rangeInferLoading.value = false
  }
}

async function handleInfer() {
  const message = validateInferForm()

  if (message) {
    inferError.value = message
    inferResult.value = null
    return
  }

  inferLoading.value = true
  inferError.value = ''
  inferResult.value = null

  try {
    const result = await inferPrediction(buildInferPayload())
    inferResult.value = normalizeLatest(normalizePayload(result))
    await fetchPredictionData()
  } catch (error) {
    inferError.value = error.message || '风险推理失败，请稍后重试'
  } finally {
    inferLoading.value = false
  }
}

function validateFilters() {
  if (!filters.deviceId) {
    return '设备编号不能为空'
  }

  if (!filters.startTime) {
    return '开始时间不能为空'
  }

  if (!filters.endTime) {
    return '结束时间不能为空'
  }

  if (filters.startTime >= filters.endTime) {
    return '开始时间必须早于结束时间'
  }

  return ''
}

function validateInferForm() {
  if (!inferForm.deviceId) {
    return '风险推理的设备编号不能为空'
  }

  if (!inferForm.tsEnd) {
    return '风险推理的 ts_end 不能为空'
  }

  if (!inferForm.windowMinutes) {
    return '风险推理的 window_minutes 不能为空'
  }

  const windowMinutes = Number.parseInt(inferForm.windowMinutes, 10)
  if (!Number.isFinite(windowMinutes) || windowMinutes <= 0) {
    return '风险推理的 window_minutes 必须为正整数'
  }

  return ''
}

function validateRangeInferForm() {
  if (!rangeInferForm.deviceCode) {
    return '区间推理的设备编号不能为空'
  }

  if (!rangeInferForm.endTime) {
    return '区间推理的预测结束时间不能为空'
  }

  const lookbackMinutes = parsePositiveInteger(rangeInferForm.lookbackMinutes)
  if (lookbackMinutes === null) {
    return '回看时长必须为正整数'
  }

  if (lookbackMinutes > 180) {
    return '回看时长过大，建议不超过 180 分钟'
  }

  const inferenceStrideSeconds = parsePositiveInteger(rangeInferForm.inferenceStrideSeconds)
  if (inferenceStrideSeconds === null) {
    return '推理步长必须为正整数'
  }

  if (inferenceStrideSeconds < 10) {
    return '步长过小可能导致推理时间较长，请使用不少于 10 秒的推理步长'
  }

  const mcSamples = parsePositiveInteger(rangeInferForm.mcSamples)
  if (mcSamples === null) {
    return 'MC 采样次数必须为正整数'
  }

  if (rangeInferForm.generateAlert && !rangeInferForm.persist) {
    return '生成告警需要保存风险结果，请先勾选保存结果。'
  }

  return ''
}

function buildQueryParams() {
  return {
    device_id: filters.deviceId,
    start_time: filters.startTime,
    end_time: filters.endTime
  }
}

function buildInferPayload() {
  return {
    device_id: inferForm.deviceId,
    ts_end: inferForm.tsEnd,
    window_minutes: Number.parseInt(inferForm.windowMinutes, 10)
  }
}

function buildRangeInferPayload() {
  return {
    device_code: rangeInferForm.deviceCode,
    end_time: rangeInferForm.endTime,
    lookback_minutes: Number.parseInt(rangeInferForm.lookbackMinutes, 10),
    inference_stride_seconds: Number.parseInt(rangeInferForm.inferenceStrideSeconds, 10),
    mc_samples: Number.parseInt(rangeInferForm.mcSamples, 10),
    persist: Boolean(rangeInferForm.persist),
    generate_alert: Boolean(rangeInferForm.generateAlert)
  }
}

function normalizePayload(result) {
  let payload = result

  if (payload && typeof payload === 'object' && 'code' in payload && payload.data == null) {
    return null
  }

  while (
    payload &&
    typeof payload === 'object' &&
    payload.data &&
    typeof payload.data === 'object' &&
    payload.data !== payload
  ) {
    payload = payload.data
  }

  return payload
}

function normalizeLatest(record) {
  if (!record || typeof record !== 'object') {
    return null
  }

  return {
    risk_result_id: record.risk_result_id ?? null,
    device_id: record.device_id ?? null,
    device_code: record.device_code || '',
    sample_index: record.sample_index ?? null,
    ts_end: record.ts_end || '',
    window_minutes: toFiniteNumber(record.window_minutes),
    risk_raw: toFiniteNumber(record.risk_raw),
    risk_score: getRiskScore(record),
    risk_raw_std: toFiniteNumber(record.risk_raw_std),
    health_score: toFiniteNumber(record.health_score),
    health_level: record.health_level || '',
    health_status: record.health_status || '',
    risk_std: toFiniteNumber(record.risk_std),
    threshold: toFiniteNumber(record.threshold),
    predicted_label: record.predicted_label ?? '',
    alert_generated: Boolean(record.alert_generated),
    alert_level: record.alert_level || '',
    alert_status: record.alert_status || '',
    alert_status_text: record.alert_status_text || '',
    alert_message: record.alert_message || '',
    alert_advice: record.alert_advice || '',
    alert_id: record.alert_id ?? '',
    condition_label: record.condition_label || '',
    model_name: record.model_name || '',
    model_version: record.model_version || '',
    calibration_enabled: record.calibration_enabled,
    calibration_method: record.calibration_method || '',
    uncertainty_enabled: record.uncertainty_enabled,
    uncertainty_method: record.uncertainty_method || '',
    mc_samples: record.mc_samples ?? '',
    data_source: record.data_source || '',
    window_start_time: record.window_start_time || '',
    window_end_time: record.window_end_time || '',
    created_at: record.created_at || ''
  }
}

function normalizeHistory(records) {
  const sourceRecords = extractHistoryRecords(records)

  return sourceRecords
    .map((item) => normalizeLatest(item))
    .filter((item) => item && (item.window_end_time || item.window_start_time))
    .sort((a, b) => getRecordTime(a).localeCompare(getRecordTime(b)))
}

function normalizeHealthCurve(payload) {
  const sourceRecords = extractHistoryRecords(payload)

  return sourceRecords
    .map((item, index) => normalizeHealthCurvePoint(item, index))
    .filter((item) => item && item.time)
    .sort((a, b) => getRecordTime(a).localeCompare(getRecordTime(b)))
}

function normalizeHealthCurvePoint(item, index) {
  const source = item && typeof item === 'object' ? item : {}
  const time = source.time || source.window_end_time || source.ts_end || source.created_at || ''
  const riskScoreSmoothed = toFiniteNumber(source.risk_score_smoothed)
  const healthScoreSmoothed = toFiniteNumber(source.health_score_smoothed)

  return {
    key: `${time}-${source.risk_result_id ?? index}`,
    risk_result_id: source.risk_result_id ?? null,
    device_id: source.device_id ?? null,
    device_code: source.device_code || '',
    time,
    ts_end: source.ts_end || '',
    window_start_time: source.window_start_time || '',
    window_end_time: source.window_end_time || '',
    created_at: source.created_at || '',
    risk_score_raw: toFiniteNumber(source.risk_score_raw),
    risk_score_smoothed: riskScoreSmoothed,
    risk_score: riskScoreSmoothed,
    health_score_raw: toFiniteNumber(source.health_score_raw),
    health_score_smoothed: healthScoreSmoothed,
    health_score: healthScoreSmoothed,
    risk_std: toFiniteNumber(source.risk_std),
    threshold: toFiniteNumber(source.threshold),
    predicted_label: source.predicted_label ?? '',
    health_level: source.health_level || '',
    health_status: source.health_status || '',
    health_description: source.health_description || '',
    condition_label: source.condition_label || '',
    model_version: source.model_version || ''
  }
}

function normalizeRangeInferResult(record) {
  if (!record || typeof record !== 'object') {
    return null
  }

  const riskSeries = Array.isArray(record.risk_series)
    ? record.risk_series.map((item, index) => normalizeRangeRiskPoint(item, index))
    : []
  const healthSeries = Array.isArray(record.health_series)
    ? record.health_series.map((item, index) => normalizeRangeHealthPoint(item, index))
    : []

  return {
    device_code: record.device_code || '',
    start_time: record.start_time || '',
    end_time: record.end_time || '',
    lookback_minutes: toFiniteNumber(record.lookback_minutes),
    inference_stride_seconds: toFiniteNumber(record.inference_stride_seconds),
    mc_samples: toFiniteNumber(record.mc_samples),
    monitor_query_start_time: record.monitor_query_start_time || '',
    monitor_point_count: toFiniteNumber(record.monitor_point_count),
    total_candidate_points: toFiniteNumber(record.total_candidate_points),
    result_count: toFiniteNumber(record.result_count),
    saved_count: toFiniteNumber(record.saved_count),
    skipped_existing_count: toFiniteNumber(record.skipped_existing_count),
    skipped_window_count: toFiniteNumber(record.skipped_window_count),
    model_name: record.model_name || '',
    model_version: record.model_version || '',
    calibration_enabled: record.calibration_enabled,
    calibration_method: record.calibration_method || '',
    uncertainty_enabled: record.uncertainty_enabled,
    uncertainty_method: record.uncertainty_method || '',
    risk_series: riskSeries,
    health_series: healthSeries,
    skipped_windows: Array.isArray(record.skipped_windows) ? record.skipped_windows : [],
    generate_alert: Boolean(record.generate_alert),
    alert_generation_skipped: Boolean(record.alert_generation_skipped),
    alert_generation_skip_reason: record.alert_generation_skip_reason || '',
    alert_suppress_window_minutes: toFiniteNumber(record.alert_suppress_window_minutes),
    alert_count: toFiniteNumber(record.alert_count),
    existing_alert_count: toFiniteNumber(record.existing_alert_count),
    suppressed_alert_count: toFiniteNumber(record.suppressed_alert_count),
    alert_segment_count: toFiniteNumber(record.alert_segment_count),
    alerts: Array.isArray(record.alerts) ? record.alerts : [],
    alert_segments: Array.isArray(record.alert_segments) ? record.alert_segments : []
  }
}

function normalizeRangeAlert(record, index) {
  const source = record && typeof record === 'object' ? record : {}

  return {
    key: `${source.alert_id ?? 'alert'}-${source.risk_result_id ?? index}`,
    alert_id: source.alert_id ?? null,
    risk_result_id: source.risk_result_id ?? null,
    device_code: source.device_code || '',
    alert_level: source.alert_level || '',
    alert_status: source.alert_status || '',
    alert_status_text: source.alert_status_text || '',
    risk_score: getRiskScore(source),
    health_score: toFiniteNumber(source.health_score),
    health_level: source.health_level || '',
    health_status: source.health_status || '',
    alert_time: source.alert_time || '',
    alert_message: source.alert_message || source.message || '',
    alert_advice: source.alert_advice || ''
  }
}

function normalizeRangeAlertSegment(record, index) {
  const source = record && typeof record === 'object' ? record : {}

  return {
    key: `${source.segment_start_time || 'segment'}-${source.alert_level || 'level'}-${index}`,
    device_code: source.device_code || '',
    alert_level: source.alert_level || '',
    segment_start_time: source.segment_start_time || '',
    segment_end_time: source.segment_end_time || '',
    point_count: toFiniteNumber(source.point_count),
    max_risk_score: toFiniteNumber(source.max_risk_score),
    representative_time: source.representative_time || '',
    representative_risk_result_id: source.representative_risk_result_id ?? null,
    suppressed: Boolean(source.suppressed),
    suppress_reason: source.suppress_reason || '',
    alert_id: source.alert_id ?? null,
    existing_alert_id: source.existing_alert_id ?? null
  }
}

function normalizeRangeRiskPoint(item, index) {
  const source = item && typeof item === 'object' ? item : {}
  const time = source.time || source.window_end_time || ''

  return {
    key: `${time}-${source.risk_result_id ?? index}`,
    risk_result_id: source.risk_result_id ?? null,
    time,
    window_start_time: source.window_start_time || '',
    window_end_time: source.window_end_time || '',
    risk_raw: toFiniteNumber(source.risk_raw),
    risk_score: getRiskScore(source),
    risk_raw_std: toFiniteNumber(source.risk_raw_std),
    risk_std: toFiniteNumber(source.risk_std),
    threshold: toFiniteNumber(source.threshold),
    predicted_label: source.predicted_label ?? '',
    health_score: toFiniteNumber(source.health_score),
    health_level: source.health_level || '',
    health_status: source.health_status || '',
    condition_label: source.condition_label || ''
  }
}

function normalizeRangeHealthPoint(item, index) {
  const source = item && typeof item === 'object' ? item : {}
  const time = source.time || source.window_end_time || ''

  return {
    key: `${time}-${index}`,
    time,
    window_end_time: source.window_end_time || '',
    health_score: toFiniteNumber(source.health_score),
    health_level: source.health_level || '',
    health_status: source.health_status || ''
  }
}

function extractHistoryRecords(source) {
  if (Array.isArray(source)) {
    return source
  }

  if (!source || typeof source !== 'object') {
    return []
  }

  const candidates = [source.items, source.records, source.series, source.list, source.data]

  for (const item of candidates) {
    if (Array.isArray(item)) {
      return item
    }
  }

  return []
}

function getRiskScore(record) {
  const primaryValue = toFiniteNumber(record?.risk_score)
  if (primaryValue !== null) {
    return primaryValue
  }

  return toFiniteNumber(record?.calibrated_risk_score)
}

function getRecordTime(record) {
  return record?.time || record?.window_end_time || record?.ts_end || record?.created_at || record?.window_start_time || ''
}

function getRangePointTime(record) {
  return record?.time || record?.window_end_time || record?.window_start_time || ''
}

function parsePositiveInteger(value) {
  const parsedValue = Number.parseInt(value, 10)
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : null
}

function formatInteger(value) {
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? displayText(null) : Math.trunc(numericValue).toLocaleString('zh-CN')
}

function formatMinutes(value) {
  const numericValue = toFiniteNumber(value)
  return numericValue === null ? '--' : `${Math.trunc(numericValue)} 分钟`
}

function formatSuppressReason(reason) {
  const normalizedReason = reason === null || reason === undefined ? '' : String(reason).trim()
  const reasonMap = {
    same_device_level_active_alert_within_cooldown: '同设备同等级告警处于抑制窗口内',
    missing_risk_result_id: '缺少风险结果ID，无法生成告警',
    generate_alert_false: '未启用告警生成',
    persist_false: '未保存风险结果',
    risk_result_id_already_has_alert: '该风险结果已生成告警',
    alert_create_skipped: '告警创建被跳过'
  }

  return reasonMap[normalizedReason] || displayText(normalizedReason)
}

function formatSuppressedStatus(value) {
  return value ? '已抑制' : '已生成/未抑制'
}

function formatSkippedWindow(item) {
  if (!item || typeof item !== 'object') {
    return displayText(null)
  }

  return `${displayText(item.time)}：${displayText(item.reason)}`
}

function normalizeQueryDeviceId(value) {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0].trim() : ''
  }

  return typeof value === 'string' ? value.trim() : ''
}
</script>

<style scoped>
.prediction-page,
.prediction-panel,
.prediction-infer-card {
  display: grid;
  gap: var(--rail-gap-lg);
}

.prediction-filter-grid {
  grid-template-columns: minmax(140px, 0.65fr) repeat(2, minmax(240px, 1fr));
}

.prediction-main-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.72fr) minmax(0, 1.28fr);
  gap: var(--rail-gap-lg);
  align-items: start;
}

.prediction-panel,
.prediction-infer-card {
  padding: 22px;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(251, 250, 247, 0.9));
  box-shadow: var(--rail-shadow-md);
}

.prediction-side-panel {
  position: sticky;
  top: 18px;
  align-self: start;
}

.prediction-side-panel__header {
  display: grid;
  gap: 8px;
}

.prediction-side-panel__header p {
  margin: 0;
}

.prediction-overview-panel,
.prediction-chart-section,
.prediction-alert-section,
.prediction-detail-section,
.prediction-history-section {
  min-width: 0;
}

.prediction-overview-content,
.prediction-alert-content {
  display: grid;
  gap: 18px;
}

.prediction-hero-card {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  padding: 20px;
  border: 1px solid rgba(15, 108, 133, 0.18);
  border-radius: var(--rail-radius-md);
  background: linear-gradient(180deg, rgba(248, 252, 255, 0.92), rgba(255, 255, 255, 0.82));
}

.prediction-hero-card span {
  color: var(--rail-text-muted);
  font-weight: 760;
}

.prediction-hero-card strong {
  display: block;
  margin-top: 8px;
  color: var(--rail-text-strong);
  font-size: 3rem;
  line-height: 1;
}

.prediction-hero-card p {
  margin: 10px 0 0;
  color: var(--rail-text-muted);
  line-height: 1.6;
}

.prediction-summary-grid,
.prediction-mini-grid,
.prediction-alert-summary-grid {
  display: grid;
  gap: var(--rail-gap-md);
}

.prediction-summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.prediction-mini-grid,
.prediction-alert-summary-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.prediction-empty-hero {
  min-height: 190px;
  display: grid;
  place-items: center;
  text-align: center;
}

.prediction-panel__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.compact-toggle-button {
  min-height: 36px;
  padding: 0 14px;
}

.latest-compact-text {
  color: var(--rail-text-muted);
  font-weight: 720;
  line-height: 1.6;
}

.prediction-overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.prediction-chart-grid,
.prediction-infer-grid,
.range-infer-grid,
.range-chart-grid {
  display: grid;
  gap: var(--rail-gap-lg);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.prediction-infer-grid {
  grid-template-columns: minmax(140px, 0.65fr) minmax(260px, 1fr) minmax(140px, 0.5fr);
}

.range-infer-grid {
  grid-template-columns: minmax(150px, 0.75fr) minmax(250px, 1.15fr) repeat(4, minmax(130px, 0.65fr));
}

.prediction-side-panel .range-infer-grid {
  grid-template-columns: 1fr;
  gap: 14px;
}

.range-option-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.range-chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.range-checkbox-field {
  align-content: start;
}

.checkbox-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  color: var(--rail-text-strong);
  font-weight: 720;
}

.checkbox-control input {
  width: 16px !important;
  height: 16px !important;
  min-height: 16px !important;
  padding: 0 !important;
  border-radius: 4px !important;
  accent-color: var(--rail-brand);
}

.checkbox-control span {
  color: var(--rail-text-strong);
}

.field-hint {
  margin: 6px 0 0;
  color: var(--rail-text-muted);
  font-size: 0.84rem;
  font-weight: 650;
  line-height: 1.5;
}

.field-hint--warning {
  color: #b45309;
}

.prediction-infer-form {
  display: grid;
  gap: 18px;
}

.prediction-infer-form__actions {
  margin-top: 0;
}

.prediction-infer-result {
  display: grid;
  gap: 18px;
}

.range-detail-block {
  display: grid;
  gap: 12px;
}

.range-detail-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.range-detail-header h4,
.range-detail-header p {
  margin: 0;
}

.range-detail-header h4 {
  color: var(--rail-text-strong);
}

.range-detail-header p {
  margin-top: 6px;
  color: var(--rail-text-muted);
  line-height: 1.6;
}

.range-detail-table-wrap {
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-md);
  background: rgba(255, 255, 255, 0.74);
}

.range-detail-table {
  width: 100%;
  min-width: 1180px;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.range-detail-table th,
.range-detail-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--rail-border);
  text-align: left;
  white-space: nowrap;
}

.range-detail-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(248, 250, 252, 0.96);
  color: var(--rail-text-muted);
  font-weight: 760;
}

.range-detail-table td {
  color: var(--rail-text);
}

.range-alert-panel {
  padding-top: 4px;
}

.range-alert-table {
  min-width: 980px;
}

.range-alert-segment-table {
  min-width: 1160px;
}

.range-risk-detail-table {
  min-width: 1040px;
}

.range-table-message {
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.success-state {
  border-color: rgba(22, 163, 74, 0.24);
  background: rgba(240, 253, 244, 0.8);
  color: #166534;
}

.range-success-state {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.range-success-actions {
  display: inline-flex;
  gap: 10px;
  flex-wrap: wrap;
}

.range-success-link {
  min-height: 34px;
  padding: 0 12px;
  text-decoration: none;
}

.prediction-debug-card {
  background: rgba(255, 255, 255, 0.62);
}

.prediction-advanced-panel,
.prediction-debug-card {
  overflow: hidden;
}

.prediction-advanced-panel {
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-md);
  background: rgba(255, 255, 255, 0.66);
}

.prediction-advanced-panel summary,
.prediction-debug-card summary {
  cursor: pointer;
  color: var(--rail-text-strong);
  font-weight: 780;
  list-style-position: inside;
}

.prediction-advanced-panel summary {
  padding: 15px 16px;
}

.prediction-advanced-panel[open] summary {
  border-bottom: 1px solid var(--rail-border);
}

.prediction-advanced-panel .prediction-detail-groups {
  padding: 16px;
}

.prediction-debug-card summary {
  margin: -2px 0;
}

.prediction-debug-card[open] summary {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--rail-border);
}

.prediction-debug-content {
  display: grid;
  gap: 18px;
  padding-top: 16px;
}

.prediction-history-filter {
  display: grid;
  gap: 16px;
  padding: 16px;
  border-radius: var(--rail-radius-md);
}

.prediction-detail-groups {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.prediction-detail-group {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--rail-border);
  border-radius: var(--rail-radius-md);
  background: rgba(255, 255, 255, 0.62);
}

.prediction-detail-group h4 {
  margin: 0;
  color: var(--rail-text-strong);
}

.prediction-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.prediction-detail-grid div {
  min-width: 0;
}

.prediction-detail-grid dt,
.prediction-detail-grid dd {
  margin: 0;
}

.prediction-detail-grid dt {
  color: var(--rail-text-muted);
  font-size: 0.86rem;
  font-weight: 700;
}

.prediction-detail-grid dd {
  margin-top: 6px;
  color: var(--rail-text-strong);
  font-weight: 760;
  overflow-wrap: anywhere;
}

@media (max-width: 1180px) {
  .prediction-main-grid {
    grid-template-columns: 1fr;
  }

  .prediction-side-panel {
    position: static;
  }

  .prediction-overview-grid,
  .prediction-chart-grid,
  .prediction-summary-grid,
  .prediction-mini-grid,
  .prediction-alert-summary-grid,
  .range-chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .range-infer-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .prediction-panel,
  .prediction-infer-card {
    padding: 20px;
  }

  .prediction-filter-grid,
  .prediction-overview-grid,
  .prediction-chart-grid,
  .prediction-infer-grid,
  .range-infer-grid,
  .range-option-row,
  .prediction-summary-grid,
  .prediction-mini-grid,
  .prediction-alert-summary-grid,
  .range-chart-grid,
  .prediction-detail-groups,
  .prediction-detail-grid {
    grid-template-columns: 1fr;
  }

  .prediction-hero-card strong {
    font-size: 2.35rem;
  }

  .prediction-hero-card,
  .range-success-state {
    align-items: flex-start;
    flex-direction: column;
  }

  .prediction-panel__meta {
    align-items: flex-start;
  }

}
</style>
