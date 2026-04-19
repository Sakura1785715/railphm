<template>
  <section class="page-card not-found-card">
    <p class="page-tag">404</p>
    <h2>页面不存在</h2>
    <p class="page-description">
      你访问的页面当前不存在或地址输入有误，请返回首页继续浏览系统。
    </p>
    <RouterLink to="/" class="primary-link">返回首页</RouterLink>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'
</script>
