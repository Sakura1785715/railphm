<template>
  <div class="enterprise-layout">
    <aside class="enterprise-sidebar">
      <div class="brand-block">
        <div class="brand-mark">PHM</div>
        <div class="brand-content">
          <p class="brand-subtitle">RailPHM Platform</p>
          <h1>高铁列控设备故障预测与健康管理系统</h1>
          <p class="brand-description">
            面向列控设备健康评估、风险预警与运维管理的企业级平台。
          </p>
        </div>
      </div>

      <section class="nav-section">
        <div class="section-heading">业务功能</div>
        <nav class="nav-list" aria-label="主导航">
          <RouterLink
            v-for="item in LAYOUT_NAV_ITEMS"
            :key="item.to"
            :to="item.to"
            :class="['nav-item', { 'nav-item--active': isNavItemActive(item.to) }]"
          >
            <div class="nav-item__icon">
              <DashboardIcon :name="item.icon" tone="accent" size="sm" />
            </div>
            <div class="nav-item__content">
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
            </div>
          </RouterLink>
        </nav>
      </section>

      <section class="nav-section">
        <div class="section-heading">系统管理</div>
        <nav class="nav-list" aria-label="辅助导航">
          <RouterLink
            v-for="item in LAYOUT_SUPPORT_ITEMS"
            :key="item.to"
            :to="item.to"
            :class="[
              'nav-item',
              'nav-item--secondary',
              { 'nav-item--active': isNavItemActive(item.to) }
            ]"
          >
            <div class="nav-item__icon">
              <DashboardIcon :name="item.icon" tone="default" size="sm" />
            </div>
            <div class="nav-item__content">
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
            </div>
          </RouterLink>
        </nav>
      </section>

      <div class="system-card">
        <div class="system-card__header">
          <span class="system-dot"></span>
          <span>系统运行状态</span>
        </div>
        <div class="system-card__body">
          <div class="status-row">
            <span>平台框架</span>
            <strong class="status-success">正常</strong>
          </div>
          <div class="status-row">
            <span>当前阶段</span>
            <strong>基础模块联调</strong>
          </div>
          <p class="system-note">
            已完成首页总览与设备台账最小可用能力，其余业务模块按照既有架构逐步扩展。
          </p>
        </div>
      </div>
    </aside>

    <div class="enterprise-main">
      <header class="enterprise-header">
        <div class="header-left">
          <p class="header-breadcrumb">RailPHM / 工作台</p>
          <h2>{{ currentPageTitle }}</h2>
        </div>

        <div class="header-right">
          <span class="header-tag">RailPHM Platform</span>
        </div>
      </header>

      <main class="enterprise-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import DashboardIcon from '../components/dashboard/DashboardIcon.vue'
import { LAYOUT_NAV_ITEMS, LAYOUT_SUPPORT_ITEMS } from '../constants/dashboard'

const route = useRoute()
const now = ref(new Date())
let timerId = 0

const currentPageTitle = computed(() => route.meta?.title || '系统首页')

const currentTimeText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(now.value)
)

function isNavItemActive(targetPath) {
  if (targetPath === '/') {
    return route.path === targetPath
  }
  return route.path === targetPath || route.path.startsWith(`${targetPath}/`)
}

onMounted(() => {
  timerId = window.setInterval(() => {
    now.value = new Date()
  }, 60000)
})

onBeforeUnmount(() => {
  window.clearInterval(timerId)
})
</script>

<style scoped>
:root {
  color-scheme: light;
}

.enterprise-layout {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
  color: #1f2937;
}

.enterprise-sidebar {
  width: 288px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px 20px;
  background: #ffffff;
  border-right: 1px solid #e5e7eb;
}

.brand-block {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding-bottom: 20px;
  border-bottom: 1px solid #eef2f7;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: #1d4f91;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}

.brand-content h1 {
  margin: 4px 0 8px;
  font-size: 18px;
  line-height: 1.5;
  font-weight: 700;
  color: #111827;
}

.brand-subtitle {
  margin: 0;
  font-size: 12px;
  color: #1d4f91;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.brand-description {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #6b7280;
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-heading {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  letter-spacing: 0.08em;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  text-decoration: none;
  transition: all 0.2s ease;
}

.nav-item:hover {
  border-color: #cfd8e3;
  background: #f9fafb;
}

.nav-item--active {
  background: #edf4ff;
  border-color: #bfd4f3;
}

.nav-item__icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #f3f6fa;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-item--active .nav-item__icon {
  background: #dbeafe;
}

.nav-item__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.nav-item__content strong {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.nav-item__content small {
  font-size: 12px;
  line-height: 1.5;
  color: #6b7280;
}

.nav-item--secondary .nav-item__icon {
  background: #f7f8fa;
}

.system-card {
  margin-top: auto;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #f9fafb;
  overflow: hidden;
}

.system-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  background: #f3f4f6;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.system-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
}

.system-card__body {
  padding: 14px 16px 16px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
  color: #4b5563;
}

.status-row strong {
  color: #111827;
  font-weight: 600;
}

.status-success {
  color: #15803d !important;
}

.system-note {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}

.enterprise-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.enterprise-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 28px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
}

.header-left h2 {
  margin: 6px 0 0;
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.header-breadcrumb {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
  letter-spacing: 0.04em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-tag,
.header-time {
  display: inline-flex;
  align-items: center;
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
}

.header-tag {
  background: #edf4ff;
  color: #1d4f91;
  border: 1px solid #cfe0f7;
}

.header-time {
  background: #f8fafc;
  color: #475569;
  border: 1px solid #e2e8f0;
}

.enterprise-content {
  flex: 1;
  padding: 24px 28px 28px;
  overflow: auto;
}

@media (max-width: 1200px) {
  .enterprise-sidebar {
    width: 260px;
  }

  .enterprise-header {
    padding: 18px 20px;
  }

  .enterprise-content {
    padding: 20px;
  }
}

@media (max-width: 960px) {
  .enterprise-layout {
    flex-direction: column;
  }

  .enterprise-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid #e5e7eb;
  }

  .enterprise-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }

  .header-right {
    flex-wrap: wrap;
  }
}
</style>