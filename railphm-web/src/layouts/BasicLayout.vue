<template>
  <div class="basic-layout">
    <header class="layout-header">
      <div class="title-group">
        <p class="eyebrow">RailPHM 前端基础框架</p>
        <h1>高铁列控设备故障预测与健康管理系统</h1>
      </div>
      <nav class="main-nav" aria-label="主导航">
        <RouterLink to="/" class="nav-link">首页</RouterLink>
        <RouterLink to="/health" class="nav-link">系统联通测试</RouterLink>
      </nav>
    </header>

    <main class="layout-main">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>
