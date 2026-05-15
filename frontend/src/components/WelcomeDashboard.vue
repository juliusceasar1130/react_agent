<template>
  <div class="relative flex flex-1 flex-col items-center overflow-y-auto px-4 pb-20 pt-12">
    
    <!-- Hero Section: Central Search -->
    <div class="w-full max-w-3xl animate-fade-in mb-16 text-center">
      <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[28px] bg-gradient-to-br from-primary/20 via-white to-accent/20 shadow-glow">
        <svg class="h-10 w-10 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <h2 class="text-4xl font-extrabold tracking-tight text-text sm:text-5xl">
        120JPH <span class="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">AI 助手</span>
      </h2>
      <p class="mt-4 text-lg text-neutral-500">连接车间实时数据，提供物流追踪与缺陷智能分析</p>
      
      <!-- 首页核心输入框 -->
      <div class="mt-10 relative group">
        <div class="absolute -inset-1 bg-gradient-to-r from-primary/20 to-accent/20 rounded-[22px] blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
        <div class="relative flex items-center bg-white border border-neutral-200 rounded-[20px] shadow-xl p-2 pl-6 overflow-hidden transition-all duration-300 focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10">
          <svg class="h-6 w-6 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input 
            v-model="localInput"
            @keydown.enter="handleSubmit"
            type="text" 
            placeholder="在此直接提问，开启智能车间探索..." 
            class="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-lg py-3 px-4 text-text placeholder-neutral-400"
          />
          <button 
            @click="handleSubmit"
            class="bg-primary text-white h-12 w-12 rounded-2xl flex items-center justify-center hover:scale-105 active:scale-95 transition shadow-lg"
          >
            <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Capabilities Grid (Dynamic from Store) -->
    <div class="w-full max-w-6xl animate-fade-in-up">
      <div class="flex items-center gap-3 mb-8 px-2">
        <div class="h-px flex-1 bg-neutral-200"></div>
        <span class="text-xs font-bold uppercase tracking-[0.2em] text-neutral-400">
          {{ skillsStore.isLoading ? '正在加载核心能力...' : '核心能力矩阵' }}
        </span>
        <div class="h-px flex-1 bg-neutral-200"></div>
      </div>

      <div v-if="skillsStore.isLoading" class="flex justify-center py-12">
         <div class="h-10 w-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
      </div>

      <div v-else class="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div 
          v-for="domain in skillsStore.domains" 
          :key="domain.name"
          class="group relative flex flex-col rounded-[32px] border border-white/80 bg-white/60 shadow-xl backdrop-blur-xl transition-all duration-300 hover:shadow-glow hover:-translate-y-1 overflow-hidden"
        >
          <div class="p-8">
            <div class="flex items-start justify-between mb-8">
              <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/10 via-white to-accent/10 shadow-glow group-hover:scale-110 transition-transform">
                <!-- Fallback Icon if server doesn't provide one -->
                <svg class="h-8 w-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span class="rounded-full bg-neutral-100 px-3 py-1 text-[11px] font-bold tracking-wider text-neutral-500 uppercase">Domain Skill</span>
            </div>
            
            <h3 class="text-2xl font-bold text-text mb-2">{{ domain.title }}</h3>
            <p class="text-neutral-500 leading-relaxed mb-10 text-sm">{{ domain.description }}</p>
            
            <div class="space-y-6">
              <div v-for="scenario in domain.scenarios" :key="scenario.name" class="relative pl-6 border-l-2 border-neutral-100 group-hover:border-primary/20 transition-colors">
                <div class="absolute -left-[9px] top-0 h-4 w-4 rounded-full bg-white border-2 border-neutral-200 group-hover:border-primary/40 transition-colors"></div>
                <h4 class="text-sm font-bold text-neutral-800 flex items-center gap-2">
                  {{ scenario.title }}
                </h4>
                
                <div class="mt-4 grid grid-cols-1 gap-2">
                  <button 
                    v-for="(question, idx) in scenario.questions" 
                    :key="idx"
                    @click="triggerPrompt(question)"
                    class="group/btn flex items-center justify-between rounded-xl bg-neutral-50/80 px-4 py-3 text-left transition hover:bg-primary/5 hover:ring-1 hover:ring-primary/20"
                  >
                    <span class="text-sm text-neutral-600 transition group-hover/btn:text-primary leading-snug">"{{ question }}"</span>
                    <svg class="h-4 w-4 text-neutral-300 transition group-hover/btn:text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSkillsStore } from '@/stores/skills'

const emit = defineEmits<{
  (e: 'submit', prompt: string): void
}>()

const localInput = ref('')
const skillsStore = useSkillsStore()

onMounted(() => {
  skillsStore.fetchSkills()
})

const handleSubmit = () => {
  if (!localInput.value.trim()) return
  emit('submit', localInput.value.trim())
  localInput.value = ''
}

const triggerPrompt = (prompt: string) => {
  emit('submit', prompt)
}
</script>
