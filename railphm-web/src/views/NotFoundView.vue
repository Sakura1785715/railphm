<template>
  <section class="page-card not-found-card">
    <div class="page-heading">
      <p class="page-tag">404</p>
      <h2>页面不存在</h2>
      <p class="page-description">
        你访问的页面当前不存在，或该业务入口尚未在 RailPHM 中注册。请返回系统首页继续查看设备健康管理相关功能。
      </p>
    </div>

    <div class="placeholder-grid">
      <article class="placeholder-card">
        <span class="status-pill status-pill--warning">路径无效</span>
        <h3>未匹配到页面路由</h3>
        <p>请确认浏览器地址是否正确，或从系统左侧导航重新进入目标模块。</p>
      </article>

      <article class="placeholder-card">
        <span class="status-pill status-pill--default">建议操作</span>
        <h3>返回稳定入口</h3>
        <p>系统首页、设备台账和联通测试页是当前已经建设完成的主要入口。</p>
      </article>
    </div>

    <div class="action-bar">
      <RouterLink to="/" class="primary-link">返回首页</RouterLink>
      <RouterLink to="/devices" class="secondary-link">进入设备台账</RouterLink>
    </div>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'
</script>