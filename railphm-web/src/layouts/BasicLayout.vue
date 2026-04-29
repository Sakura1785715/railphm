<template>
  <RouterView v-if="isPublicPage" />

  <div v-else class="enterprise-layout">
    <aside class="enterprise-sidebar" aria-label="系统导航">
      <div class="brand-block">
        <div class="brand-mark">PHM</div>
        <div class="brand-content">
          <p class="brand-subtitle">RailPHM Platform</p>
          <h1>高铁列控设备故障预测与健康管理系统</h1>
          <p class="brand-description">列控设备健康评估、风险预测与告警处置一体化运维平台。</p>
        </div>
      </div>

      <section class="nav-section">
        <div class="section-heading">核心业务</div>
        <nav class="nav-list" aria-label="核心业务导航">
          <RouterLink
            v-for="item in primaryNavItems"
            :key="item.path"
            :to="item.path"
            :class="['nav-item', { 'nav-item--active': isNavItemActive(item) }]"
          >
            <span class="nav-item__icon">
              <DashboardIcon :name="item.icon" tone="accent" size="sm" />
            </span>
            <span class="nav-item__content">
              <strong>{{ item.label }}</strong>
              <small>{{ item.description }}</small>
            </span>
          </RouterLink>
        </nav>
      </section>

      <section class="nav-section nav-section--secondary">
        <div class="section-heading">运维辅助</div>
        <nav class="nav-list" aria-label="运维辅助导航">
          <RouterLink
            v-for="item in secondaryNavItems"
            :key="item.path"
            :to="item.path"
            :class="['nav-item', 'nav-item--secondary', { 'nav-item--active': isNavItemActive(item) }]"
          >
            <span class="nav-item__icon">
              <DashboardIcon :name="item.icon" tone="default" size="sm" />
            </span>
            <span class="nav-item__content">
              <strong>{{ item.label }}</strong>
              <small>{{ item.description }}</small>
            </span>
          </RouterLink>
        </nav>
      </section>

      <div class="system-card">
        <div class="system-card__header">
          <span class="system-dot" aria-hidden="true"></span>
          <span>系统运行状态</span>
        </div>
        <div class="system-card__body">
          <div class="status-row">
            <span>平台框架</span>
            <strong class="status-success">正常</strong>
          </div>
          <div class="status-row">
            <span>当前角色</span>
            <strong>{{ currentRoleLabel }}</strong>
          </div>
          <p class="system-note">导航、登录态与业务页面已统一纳入 RailPHM 主框架。</p>
        </div>
      </div>
    </aside>

    <div class="enterprise-main">
      <header class="enterprise-header">
        <div class="header-left">
          <p class="header-breadcrumb">RailPHM / {{ activeModuleLabel }}</p>
          <h2>{{ currentPageTitle }}</h2>
          <p v-if="currentPageDescription" class="header-description">{{ currentPageDescription }}</p>
        </div>

        <div class="header-right">
          <span class="header-time">{{ currentTimeText }}</span>
          <span class="header-tag">上线运维框架</span>

          <div class="header-user">
            <div class="header-avatar" aria-hidden="true">{{ userInitial }}</div>
            <div class="header-user__text">
              <strong>{{ currentUserName }}</strong>
              <small>{{ currentRoleLabel }}</small>
            </div>
            <button class="header-auth-button" type="button" :disabled="loggingOut" @click="handleLogout">
              {{ loggingOut ? '退出中...' : '退出登录' }}
            </button>
          </div>
        </div>
      </header>

      <main class="enterprise-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { logout } from '../api/auth'
import DashboardIcon from '../components/dashboard/DashboardIcon.vue'
import { clearAuth, getStoredUser, getToken } from '../utils/auth'

const route = useRoute()
const router = useRouter()
const now = ref(new Date())
const currentUser = ref(getStoredUser())
const loggingOut = ref(false)
let timerId = 0

const primaryNavItems = [
  {
    path: '/',
    label: '系统首页',
    description: '运行总览与风险态势',
    icon: 'home',
    match: ['/']
  },
  {
    path: '/devices',
    label: '设备台账',
    description: '设备主数据与详情入口',
    icon: 'device',
    match: ['/devices']
  },
  {
    path: '/monitor',
    label: '运行监测',
    description: 'ATP 监测序列查询',
    icon: 'monitor',
    match: ['/monitor']
  },
  {
    path: '/predictions',
    label: '风险预测',
    description: '模型结果与趋势分析',
    icon: 'prediction',
    match: ['/predictions']
  },
  {
    path: '/alerts',
    label: '告警中心',
    description: '告警记录与处置跟踪',
    icon: 'alert',
    match: ['/alerts']
  }
]

const secondaryNavItems = [
  {
    path: '/health',
    label: '系统联通测试',
    description: '前后端健康接口验证',
    icon: 'health',
    match: ['/health']
  }
]

const allNavItems = [...primaryNavItems, ...secondaryNavItems]

const currentPageTitle = computed(() => route.meta?.title || '系统首页')
const currentPageDescription = computed(() => route.meta?.description || activeNavItem.value?.description || '')
const isPublicPage = computed(() => route.meta?.public === true)
const currentRole = computed(() => currentUser.value?.role || '')
const currentRoleLabel = computed(() => getRoleLabel(currentRole.value))
const currentUserName = computed(() => {
  if (currentUser.value?.display_name) {
    return currentUser.value.display_name
  }

  if (currentUser.value?.username) {
    return currentUser.value.username
  }

  return getToken() ? '已登录用户' : '未登录用户'
})

const userInitial = computed(() => currentUserName.value.trim().slice(0, 1).toUpperCase() || 'U')
const activeNavItem = computed(() => allNavItems.find((item) => isNavItemActive(item)) || primaryNavItems[0])
const activeModuleLabel = computed(() => activeNavItem.value?.label || currentPageTitle.value)

const currentTimeText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(now.value)
)

function isNavItemActive(item) {
  if (item.path === '/') {
    return route.path === '/'
  }

  return item.match.some((prefix) => route.path === prefix || route.path.startsWith(`${prefix}/`))
}

function getRoleLabel(role) {
  if (role === 'ADMIN') {
    return '系统管理员（ADMIN）'
  }

  if (role === 'OPS') {
    return '运维用户（OPS）'
  }

  return '角色未知'
}

async function handleLogout() {
  if (loggingOut.value) {
    return
  }

  loggingOut.value = true

  try {
    await logout()
  } catch {
    // 退出以清理本地登录态为最终准则，避免接口异常时用户无法退出。
  } finally {
    clearAuth()
    currentUser.value = null
    loggingOut.value = false
    router.replace('/login')
  }
}

watch(
  () => route.fullPath,
  () => {
    currentUser.value = getStoredUser()
  },
  { immediate: true }
)

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
.enterprise-layout {
  display: grid;
  grid-template-columns: var(--layout-sidebar-width) minmax(0, 1fr);
  min-height: 100vh;
  background: var(--color-bg-page);
  color: var(--color-text-primary);
}

.enterprise-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-6) var(--space-5);
  overflow-y: auto;
  background: #ffffff;
  border-right: 1px solid var(--color-border);
}

.brand-block {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.brand-mark {
  width: 44px;
  height: 44px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  background: var(--color-primary);
  color: var(--color-text-inverse);
  font-size: 13px;
  font-weight: 780;
  letter-spacing: 0.08em;
}

.brand-content {
  min-width: 0;
}

.brand-content h1 {
  margin: var(--space-1) 0 var(--space-2);
  color: var(--color-text-primary);
  font-size: 17px;
  font-weight: 760;
  line-height: 1.45;
}

.brand-subtitle {
  margin: 0;
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 760;
  letter-spacing: 0;
  text-transform: uppercase;
}

.brand-description {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.nav-section--secondary {
  margin-top: auto;
}

.section-heading {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: 760;
  letter-spacing: 0;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  padding: 11px 12px;
  color: var(--color-text-secondary);
  text-decoration: none;
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  background: transparent;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.nav-item:hover {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-color: var(--color-primary-border);
}

.nav-item--active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-color: var(--color-primary-border);
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.nav-item__icon {
  flex: none;
}

.nav-item__content {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.nav-item__content strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 730;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-item--active .nav-item__content strong {
  color: var(--color-primary);
}

.nav-item__content small {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  line-height: 1.45;
}

.nav-item--secondary {
  padding-block: 10px;
  background: var(--color-bg-soft);
  border-color: var(--color-border);
}

.system-card {
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: var(--color-bg-soft);
}

.system-card__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 730;
  border-bottom: 1px solid var(--color-border);
  background: #ffffff;
}

.system-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-pill);
  background: var(--color-success);
  box-shadow: 0 0 0 4px var(--color-success-soft);
}

.system-card__body {
  padding: var(--space-4);
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.status-row strong {
  color: var(--color-text-primary);
  font-weight: 730;
  text-align: right;
}

.status-success {
  color: var(--color-success) !important;
}

.system-note {
  margin: var(--space-3) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-relaxed);
}

.enterprise-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.enterprise-header {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-5);
  padding: var(--space-5) var(--space-6);
  background: rgba(255, 255, 255, 0.94);
  border-bottom: 1px solid var(--color-border);
  backdrop-filter: blur(12px);
}

.header-left {
  min-width: 0;
}

.header-breadcrumb,
.header-description {
  margin: 0;
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

.header-breadcrumb {
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 760;
  letter-spacing: 0;
}

.header-left h2 {
  margin: var(--space-1) 0 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-xl);
  font-weight: 780;
  line-height: 1.25;
}

.header-description {
  max-width: 760px;
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
}

.header-right {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.header-tag,
.header-time {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  font-weight: 690;
  white-space: nowrap;
}

.header-tag {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary-border);
}

.header-time {
  color: var(--color-text-secondary);
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
}

.header-user {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 6px 8px 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: #ffffff;
  box-shadow: var(--shadow-sm);
}

.header-avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-pill);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  font-weight: 800;
}

.header-user__text {
  display: grid;
  gap: 1px;
  min-width: 88px;
  text-align: left;
}

.header-user__text strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: 760;
  line-height: 1.3;
}

.header-user__text small {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: 690;
  line-height: 1.3;
}

.header-auth-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 760;
  white-space: nowrap;
}

.header-auth-button:hover:not(:disabled) {
  border-color: var(--color-primary-border);
  background: var(--color-primary-soft);
}

.header-auth-button:disabled {
  opacity: 0.62;
}

.enterprise-content {
  flex: 1;
  min-width: 0;
  padding: var(--space-6);
  overflow: auto;
  background: var(--color-bg-page);
}

@media (max-width: 1280px) {
  .enterprise-layout {
    grid-template-columns: 260px minmax(0, 1fr);
  }

  .enterprise-sidebar {
    padding: var(--space-5) var(--space-4);
  }

  .brand-description,
  .nav-item__content small {
    display: none;
  }
}

@media (max-width: 960px) {
  .enterprise-layout {
    display: flex;
    flex-direction: column;
  }

  .enterprise-sidebar {
    position: static;
    width: 100%;
    height: auto;
    padding: var(--space-4);
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .brand-block {
    align-items: center;
    padding-bottom: var(--space-4);
  }

  .brand-content h1 {
    margin-bottom: 0;
    font-size: 16px;
  }

  .nav-section,
  .nav-section--secondary {
    margin-top: 0;
  }

  .nav-list {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .nav-item {
    min-height: 58px;
  }

  .system-card {
    display: none;
  }

  .enterprise-main {
    height: auto;
    min-height: 0;
    overflow: visible;
  }

  .enterprise-header {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--space-4);
  }

  .header-right {
    width: 100%;
    justify-content: flex-start;
  }

  .enterprise-content {
    padding: var(--space-4);
    overflow: visible;
  }
}

@media (max-width: 720px) {
  .nav-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .header-time,
  .header-tag {
    display: none;
  }

  .header-user {
    width: 100%;
    align-items: center;
  }

  .header-user__text {
    flex: 1;
  }
}

@media (max-width: 520px) {
  .brand-content h1 {
    font-size: 15px;
  }

  .nav-list {
    grid-template-columns: 1fr;
  }
}
</style>
