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
      <p class="mt-4 text-lg text-neutral-500">连接油漆车间实时数据，提供物流追踪与缺陷智能分析</p>
      
      <!-- 首页核心输入框 (模拟) -->
      <div class="mt-10 relative group">
        <div class="absolute -inset-1 bg-gradient-to-r from-primary/20 to-accent/20 rounded-[22px] blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
        <div class="relative flex items-center bg-white border border-neutral-200 rounded-[20px] shadow-xl p-2 pl-6 overflow-hidden transition-all duration-300 focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10">
          <svg class="h-6 w-6 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input 
            v-model="localInput"
            @keydown.enter="handleHeroSubmit"
            type="text" 
            placeholder="在此直接提问，如：查询当前涂装二线的滞留车辆..." 
            class="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-lg py-3 px-4 text-text placeholder-neutral-400"
          />
          <button 
            @click="handleHeroSubmit"
            class="bg-primary text-white h-12 w-12 rounded-2xl flex items-center justify-center hover:scale-105 active:scale-95 transition shadow-lg"
          >
            <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Capabilities Grid -->
    <div class="w-full max-w-6xl animate-fade-in-up">
      <div class="flex items-center gap-3 mb-8 px-2">
        <div class="h-px flex-1 bg-neutral-200"></div>
        <span class="text-xs font-bold uppercase tracking-[0.2em] text-neutral-400">核心能力矩阵</span>
        <div class="h-px flex-1 bg-neutral-200"></div>
      </div>

      <div class="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div 
          v-for="domain in domains" 
          :key="domain.name"
          class="group relative flex flex-col rounded-[32px] border border-neutral-200/60 bg-white/60 shadow-sm backdrop-blur-xl transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
        >
          <div class="p-8">
            <div class="flex items-start justify-between mb-8">
              <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-md border border-neutral-100 group-hover:scale-110 transition-transform">
                <svg class="h-8 w-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" v-html="domain.icon"></svg>
              </div>
              <span class="rounded-full bg-neutral-100 px-3 py-1 text-[11px] font-bold tracking-wider text-neutral-500 uppercase">Domain Skill</span>
            </div>
            
            <h3 class="text-2xl font-bold text-text mb-2">{{ domain.title }}</h3>
            <p class="text-neutral-500 leading-relaxed mb-10">{{ domain.description }}</p>
            
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

    <!-- Mock Interaction Overlay -->
    <div v-if="isCreating" class="fixed inset-0 z-[100] flex items-center justify-center bg-white/80 backdrop-blur-md animate-fade-in">
      <div class="text-center">
        <div class="flex justify-center mb-6">
          <div class="h-16 w-16 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        </div>
        <h3 class="text-xl font-bold text-text">正在为您开启新对话...</h3>
        <p class="text-neutral-500 mt-2">初始化车间数据上下文，请稍候</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const localInput = ref('')
const isCreating = ref(false)

const domains = [
  {
    name: 'paint_shop_vehicle_logistics',
    title: '车辆物流追踪',
    description: '实时查询车身在油漆车间的物理位置、轨迹与排产物流状态。',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0" />',
    scenarios: [
      { 
        title: '滞留车辆监控', 
        questions: ['查询当前在各区域滞留超过2小时的车辆有哪些？', '目前面漆二线有没有滞留的白色车辆？'] 
      },
      { 
        title: '在制品追踪', 
        questions: ['显示当前电泳和面漆区域的在制品数量。', '目前面漆区域 WIP 是否超过预警阈值？'] 
      }
    ]
  },
  {
    name: 'paint_shop_defect_analysis',
    title: '缺陷智能分析',
    description: '通过历史数据深度挖掘与分析面漆、电泳的常见缺陷分布及趋势。',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />',
    scenarios: [
      { 
        title: 'Top缺陷分析', 
        questions: ['分析昨天 Top 3 的缺陷类型及主要发生区域。', '本周右前门区域最常发生的缺陷是什么？'] 
      },
      { 
        title: '色差问题诊断', 
        questions: ['对比本周白色车和黑色车的色差合格率。', '最近三天哪种颜色的色差不合格率最高？'] 
      }
    ]
  }
]

const triggerPrompt = (prompt: string) => {
  mockCreateFlow(prompt)
}

const handleHeroSubmit = () => {
  if (!localInput.value.trim()) return
  mockCreateFlow(localInput.value)
}

const mockCreateFlow = (prompt: string) => {
  isCreating.value = true
  setTimeout(() => {
    isCreating.value = false
    alert(`【原型演示】\n\n系统检测到首页提问：\n"${prompt}"\n\n逻辑执行：\n1. 调用 POST /sessions 创建新会话\n2. 自动跳转到聊天视图\n3. 自动发送该消息\n\n(由于是原型，这里仅做逻辑确认)`)
  }, 1500)
}
</script>
