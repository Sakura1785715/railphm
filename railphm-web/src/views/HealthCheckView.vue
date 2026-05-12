<template>
  <section class="page-card">
    <PageHeader
      eyebrow="前后端联调"
      title="系统联通测试"
      description="该页面会请求后端健康检查接口 /api/v1/health，用于验证当前前端与 railphm-server 是否联通正常。"
    >
      <template #actions>
        <button class="primary-button" type="button" @click="loadHealthStatus" :disabled="loading">
          {{ loading ? '检测中...' : '重新检测' }}
        </button>
      </template>
    </PageHeader>

    <div class="system-state-grid">
      <StatCard
        label="服务健康状态"
        :value="healthStateLabel"
        :description="healthStateDescription"
        :type="healthStateType"
        :loading="loading"
      >
        <template #extra>
          <StatusTag :label="healthStateLabel" :type="healthStateType" />
        </template>
      </StatCard>

      <StatCard
        label="接口地址"
        value="/api/v1/health"
        description="保持当前 Axios 请求封装与 Vite 代理配置不变，仅对页面视觉进行统一包装。"
        type="neutral"
      />

      <StatCard
        label="运维辅助"
        value="联调入口"
        description="用于快速判断前端、代理和后端服务是否处于可联通状态。"
        type="info"
      />
    </div>

    <ActionBar align="left">
      <span class="status-hint">
        {{ loading ? '正在请求后端健康接口' : '可手动重新发起检测' }}
      </span>
    </ActionBar>

    <LoadingBlock v-if="loading" text="正在进行前后端联通检测，请稍候..." />

    <ErrorState
      v-else-if="errorMessage"
      title="联通失败"
      :message="errorMessage"
      retry-text="重新检测"
      @retry="loadHealthStatus"
    >
      <p class="subtle-text">
        请确认 railphm-server 已启动，并检查前端环境变量中的接口地址或代理目标配置。
      </p>
    </ErrorState>

    <div v-else-if="healthResult" class="result-grid">
      <SectionCard title="接口返回状态" class="result-panel">
        <dl class="data-list">
          <InfoRow label="业务代码" :value="healthResult.code" empty-text="未返回" />
          <InfoRow label="消息" :value="healthResult.message" empty-text="未返回" />
          <InfoRow label="服务名" :value="healthResult.data?.service" empty-text="未返回" />
          <InfoRow label="运行状态" :value="healthResult.data?.status" empty-text="未返回" />
          <InfoRow label="版本" :value="healthResult.data?.version" empty-text="未返回" />
        </dl>
      </SectionCard>

      <SectionCard title="原始响应" class="result-panel">
        <pre class="response-preview">{{ formattedResult }}</pre>
      </SectionCard>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getHealthStatus } from '../api/health'
import {
  ActionBar,
  ErrorState,
  InfoRow,
  LoadingBlock,
  PageHeader,
  SectionCard,
  StatCard,
  StatusTag
} from '../components/common'

const loading = ref(false)
const errorMessage = ref('')
const healthResult = ref(null)

const formattedResult = computed(() =>
  healthResult.value ? JSON.stringify(healthResult.value, null, 2) : ''
)

const healthStateType = computed(() => {
  if (loading.value) return 'neutral'
  if (errorMessage.value) return 'danger'
  if (healthResult.value) return 'success'
  return 'neutral'
})

const healthStateLabel = computed(() => {
  if (loading.value) return '检测中'
  if (errorMessage.value) return '联通失败'
  if (healthResult.value) return '联通正常'
  return '待检测'
})

const healthStateDescription = computed(() =>
  loading.value ? '正在请求后端健康接口。' : errorMessage.value || '健康检查接口已返回稳定响应。'
)

async function loadHealthStatus() {
  loading.value = true
  errorMessage.value = ''

  try {
    healthResult.value = await getHealthStatus()
  } catch (error) {
    healthResult.value = null
    errorMessage.value = error.message || '联通检测失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadHealthStatus()
})
</script>
