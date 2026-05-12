<template>
  <section class="page-card not-found-card">
    <PageHeader
      eyebrow="404"
      title="页面不存在"
      description="你访问的页面当前不存在，或该业务入口尚未在 RailPHM 中注册。请返回系统首页继续查看设备健康管理相关功能。"
    />

    <div class="placeholder-grid">
      <SectionCard title="未匹配到页面路由" class="placeholder-card">
        <template #headerActions>
          <StatusTag label="路径无效" type="warning" />
        </template>
        <p>请确认浏览器地址是否正确，或从系统左侧导航重新进入目标模块。</p>
      </SectionCard>

      <SectionCard title="返回稳定入口" class="placeholder-card">
        <template #headerActions>
          <StatusTag label="建议操作" type="neutral" />
        </template>
        <p>系统首页、设备台账和联通测试页是当前已经建设完成的主要入口。</p>
      </SectionCard>
    </div>

    <ActionBar align="left">
      <RouterLink to="/" class="primary-link">返回首页</RouterLink>
      <RouterLink to="/devices" class="secondary-link">进入设备台账</RouterLink>
    </ActionBar>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { ActionBar, PageHeader, SectionCard, StatusTag } from '../components/common'
</script>
