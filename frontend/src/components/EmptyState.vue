<!-- 2025-01-07 - 空状态美化：渐变图标与优雅布局 -->
<template>
  <div class="flex-1 flex items-center justify-center bg-gradient-to-br from-bg via-surface to-primary/5">
    <div class="text-center animate-fade-in">
      <div class="relative inline-flex items-center justify-center mb-6">
        <div class="absolute inset-0 bg-gradient-to-br from-primary to-primary-hover rounded-3xl blur-2xl opacity-20 animate-pulse"></div>
        <div class="relative w-24 h-24 rounded-3xl bg-gradient-to-br from-primary/10 to-secondary/10 flex items-center justify-center">
          <svg class="w-12 h-12 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
      </div>
      <h2 class="text-2xl font-semibold text-text mb-2">欢迎使用 AI 助手</h2>
      <p class="text-neutral-500 max-w-xs mx-auto">在左侧创建新会话或选择现有会话开始对话</p>
    </div>
  </div>
</template>
