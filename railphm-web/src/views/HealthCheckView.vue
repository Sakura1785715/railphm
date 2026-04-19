<template>
  <section class="page-card">
    <div class="page-heading">
      <p class="page-tag">前后端联调</p>
      <h2>系统联通测试</h2>
      <p class="page-description">
        该页面会请求后端健康检查接口 <code>/api/v1/health</code>，用于验证当前前端与
        <code>railphm-server</code> 是否联通正常。
      </p>
    </div>

    <div class="action-bar">
      <button class="primary-button" type="button" @click="loadHealthStatus" :disabled="loading">
        {{ loading ? '检测中...' : '重新检测' }}
      </button>
      <span class="status-hint">
        {{ loading ? '正在请求后端健康接口' : '可手动重新发起检测' }}
      </span>
    </div>

    <div v-if="loading" class="state-panel loading-state">
      正在进行前后端联通检测，请稍候...
    </div>

    <div v-else-if="errorMessage" class="state-panel error-state">
      <h3>联通失败</h3>
      <p>{{ errorMessage }}</p>
      <p class="subtle-text">
        请确认 `railphm-server` 已启动，并检查前端环境变量中的接口地址或代理目标配置。
      </p>
    </div>

    <div v-else-if="healthResult" class="result-grid">
      <article class="result-panel">
        <h3>接口返回状态</h3>
        <dl class="data-list">
          <div>
            <dt>业务代码</dt>
            <dd>{{ healthResult.code }}</dd>
          </div>
          <div>
            <dt>消息</dt>
            <dd>{{ healthResult.message }}</dd>
          </div>
          <div>
            <dt>服务名</dt>
            <dd>{{ healthResult.data?.service || '未返回' }}</dd>
          </div>
          <div>
            <dt>运行状态</dt>
            <dd>{{ healthResult.data?.status || '未返回' }}</dd>
          </div>
          <div>
            <dt>版本</dt>
            <dd>{{ healthResult.data?.version || '未返回' }}</dd>
          </div>
        </dl>
      </article>

      <article class="result-panel">
        <h3>原始响应</h3>
        <pre class="response-preview">{{ formattedResult }}</pre>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getHealthStatus } from '../api/health'

const loading = ref(false)
const errorMessage = ref('')
const healthResult = ref(null)

const formattedResult = computed(() =>
  healthResult.value ? JSON.stringify(healthResult.value, null, 2) : ''
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
