<template>
  <section class="device-detail-page">
    <div class="device-detail-topbar">
      <div class="device-detail-topbar__content">
        <p class="page-tag">设备详情</p>
        <h2>设备详情</h2>
        <p class="page-description">
          查看单台设备的基础档案信息，当前字段口径与设备台账列表保持一致。
        </p>
      </div>

      <div class="device-detail-topbar__actions">
        <span v-if="device" class="device-detail-topbar__chip">设备 ID {{ device.device_id }}</span>
        <RouterLink :to="backToList" class="secondary-link">返回设备台账</RouterLink>
      </div>
    </div>

    <div v-if="loading" class="state-panel loading-state">
      正在加载设备详情，请稍候...
    </div>

    <div v-else-if="errorMessage" :class="['state-panel', isNotFound ? 'empty-state' : 'error-state']">
      <h3>{{ isNotFound ? '未找到对应设备' : '设备详情加载失败' }}</h3>
      <p>{{ errorMessage }}</p>
      <p class="subtle-text">
        {{ isNotFound ? '请返回设备台账重新选择设备。' : '可返回列表后重试，或检查后端服务状态。' }}
      </p>
      <div class="action-bar">
        <RouterLink :to="backToList" class="primary-link">返回设备台账</RouterLink>
      </div>
    </div>

    <DeviceDetailPanel v-else-if="device" :device="device" />
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import DeviceDetailPanel from '../components/device/DeviceDetailPanel.vue'
import { getDeviceDetail } from '../api/device'

const route = useRoute()

const loading = ref(false)
const device = ref(null)
const errorMessage = ref('')
const isNotFound = ref(false)

const backToList = computed(() => ({
  name: 'devices',
  query: route.query
}))

watch(
  () => route.params.id,
  async () => {
    await loadDeviceDetail()
  },
  {
    immediate: true
  }
)

async function loadDeviceDetail() {
  loading.value = true
  device.value = null
  errorMessage.value = ''
  isNotFound.value = false

  try {
    const result = await getDeviceDetail(route.params.id)
    device.value = result.data || null
  } catch (error) {
    device.value = null
    isNotFound.value = error.response?.status === 404 || error.response?.data?.code === 404
    errorMessage.value = isNotFound.value
      ? `未找到设备 ID 为 ${route.params.id} 的台账记录。`
      : error.message || '设备详情加载失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.device-detail-page {
  display: grid;
  gap: 20px;
}

.device-detail-topbar,
.device-detail-topbar__actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.device-detail-topbar {
  padding: 6px 4px 0;
}

.device-detail-topbar__actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.device-detail-topbar__chip {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid #d7e1ee;
  color: #45617f;
  font-weight: 600;
}

@media (max-width: 768px) {
  .device-detail-topbar,
  .device-detail-topbar__actions {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
