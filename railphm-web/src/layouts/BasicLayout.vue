<template>
  <div class="basic-layout">
    <aside class="layout-sidebar">
      <div class="sidebar-brand">
        <p class="sidebar-brand__eyebrow">RailPHM</p>
        <h1>高铁列控设备故障预测与健康管理系统</h1>
        <p class="sidebar-brand__description">聚焦设备健康管理、风险评估与运维辅助的企业级工作台。</p>
      </div>

      <div class="sidebar-section">
        <p class="sidebar-section__title">核心模块</p>
        <nav class="sidebar-nav" aria-label="主导航">
          <RouterLink
            v-for="item in LAYOUT_NAV_ITEMS"
            :key="item.to"
            :to="item.to"
            :class="['sidebar-nav__item', { 'sidebar-nav__item--active': isNavItemActive(item.to) }]"
          >
            <DashboardIcon :name="item.icon" tone="accent" size="sm" />
            <span class="sidebar-nav__content">
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
            </span>
          </RouterLink>
        </nav>
      </div>

      <div class="sidebar-section">
        <p class="sidebar-section__title">联调与辅助</p>
        <nav class="sidebar-nav" aria-label="辅助导航">
          <RouterLink
            v-for="item in LAYOUT_SUPPORT_ITEMS"
            :key="item.to"
            :to="item.to"
            :class="[
              'sidebar-nav__item',
              'sidebar-nav__item--secondary',
              { 'sidebar-nav__item--active': isNavItemActive(item.to) }
            ]"
          >
            <DashboardIcon :name="item.icon" tone="default" size="sm" />
            <span class="sidebar-nav__content">
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
            </span>
          </RouterLink>
        </nav>
      </div>

      <div class="sidebar-status">
        <span class="status-pill status-pill--success">系统框架在线</span>
        <p>当前工作区已接入首页总览与设备台账最小可用能力，后续模块仍按既有架构持续扩展。</p>
      </div>
    </aside>

    <div class="layout-main-shell">
      <header class="layout-header">
        <div class="layout-header__title">
          <p class="eyebrow">RailPHM 工作台</p>
          <h2>{{ route.meta?.title || '系统首页' }}</h2>
        </div>

        <div class="layout-header__meta">
          <span class="header-chip">工业运维平台</span>
          <span class="header-chip header-chip--time">{{ currentTimeText }}</span>
        </div>
      </header>

      <main class="layout-main">
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
