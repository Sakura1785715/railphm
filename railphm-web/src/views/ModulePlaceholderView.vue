<template>
  <section class="page-card module-placeholder">
    <div class="page-heading">
      <p class="page-tag">模块预留</p>
      <h2>{{ route.meta.title }}</h2>
      <p class="page-description">
        {{ route.meta.description }}
      </p>
    </div>

    <div class="state-panel empty-state">
      当前模块的正式业务页面将在后续任务继续建设。当前阶段已保留清晰路由入口，便于继续扩展。
    </div>

    <div class="action-bar">
      <RouterLink to="/" class="primary-link">返回系统首页</RouterLink>
      <RouterLink to="/health" class="secondary-link">查看系统联通测试</RouterLink>
    </div>
  </section>
</template>

<script setup>
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
</script>
