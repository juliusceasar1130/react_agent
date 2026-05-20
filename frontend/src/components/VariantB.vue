<template>
  <div class="relative flex h-full w-full overflow-hidden">
    <!-- 移动端侧边栏遮罩 -->
    <div
      v-if="isSidebarOpen"
      class="fixed inset-0 z-30 bg-neutral-900/35 backdrop-blur-[2px] lg:hidden"
      @click="$emit('closeSidebar')"
    ></div>

    <!-- 侧边栏 (保持纯聊天历史) -->
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-[18.5rem] max-w-[86vw] flex-col border-r border-neutral-200/80 bg-white/95 shadow-2xl backdrop-blur-xl transition-transform duration-200 lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:bg-white/80 lg:shadow-none shrink-0"
      :class="
        isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      "
    >
      <div
        class="flex items-center justify-between border-b border-neutral-200/80 px-4 py-4 sm:px-5 shrink-0"
      >
        <div class="flex items-center gap-3">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent shadow-glow"
          >
            <svg
              class="h-5 w-5 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.22em] text-neutral-400"
            >
              RESEARCH
            </p>
            <h2 class="text-lg font-bold text-text">智能分析助手</h2>
          </div>
        </div>

        <div class="flex items-center gap-1.5">
          <slot name="sidebar-header-action"></slot>
          <button
            class="flex h-10 w-10 items-center justify-center rounded-2xl border border-neutral-200 bg-white text-neutral-500 transition hover:border-neutral-300 hover:text-text lg:hidden"
            @click="$emit('closeSidebar')"
          >
            <svg
              class="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      <div
        class="border-b border-neutral-200/70 px-4 py-3 text-xs text-neutral-500 sm:px-5 shrink-0"
      >
        在这里管理您的历史会话。
      </div>
      <div class="flex-1 overflow-y-auto min-h-0">
        <slot name="sidebar-chat-list"></slot>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <div class="relative flex min-w-0 flex-1 flex-col overflow-hidden">
      <!-- 正常的聊天主区域 -->
      <slot v-if="!showBento" name="main-chat-area"></slot>

      <!-- Bento 风格的数据字典展示区 -->
      <div
        v-else
        class="flex flex-1 flex-col bg-neutral-50/50 p-6 overflow-y-auto"
      >
        <div class="mx-auto w-full max-w-5xl pt-8 pb-4">
          <div class="mb-8 flex items-start justify-between">
            <div>
              <span
                class="rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary"
                >基础信息</span
              >
              <h1
                class="mt-3 text-2xl font-black text-neutral-800 tracking-tight sm:text-3xl"
              >
                维度表
              </h1>
            </div>
            <button
              @click="$emit('toggle-bento')"
              class="flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-3 py-2 text-xs font-bold text-primary transition-all duration-200 hover:bg-primary hover:text-white shadow-glow shrink-0 mt-1"
            >
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              返回对话
            </button>
          </div>

          <!-- Bento 网格容器 -->
          <div class="grid grid-cols-1 gap-5 md:grid-cols-3">
            <!-- 载体类型 (Bento Card 1) -->
            <div
              @click="openDrawer('carrier_types')"
              class="group cursor-pointer rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/30 md:col-span-2 flex flex-col justify-between"
            >
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-2xl">🚜</span>
                  <span
                    class="rounded-full bg-neutral-100 px-2.5 py-0.5 text-[10px] font-bold text-neutral-500 font-mono"
                    >DIMENSION</span
                  >
                </div>
                <h3
                  class="mt-4 text-lg font-bold text-neutral-800 group-hover:text-primary transition"
                >
                  载体类型字典
                  <span class="text-xs font-normal text-neutral-400 font-mono"
                    >carrier_types</span
                  >
                </h3>
                <p class="mt-1.5 text-xs text-neutral-500 line-clamp-2">
                  定义涂装、总装及焊装车间物流运输中使用的标准和非标滑橇、吊具、托盘等物料承载设备，支持最大荷载配置。
                </p>
              </div>
              <div
                class="mt-6 border-t border-neutral-100 pt-4 flex items-center justify-between text-xs"
              >
                <span class="text-neutral-400 font-medium"
                  >数据样本:
                  <span class="font-mono text-neutral-600"
                    >C01 (普通滑橇), C02...</span
                  ></span
                >
                <span
                  class="text-primary font-bold inline-flex items-center gap-1 group-hover:translate-x-1 transition-transform"
                >
                  查看详情
                  <svg
                    class="h-3 w-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2.5"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </span>
              </div>
            </div>

            <!-- 平台字典 (Bento Card 2) -->
            <div
              @click="openDrawer('vehicle_platforms')"
              class="group cursor-pointer rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/30 flex flex-col justify-between"
            >
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-2xl">🔌</span>
                  <span
                    class="rounded-full bg-neutral-100 px-2.5 py-0.5 text-[10px] font-bold text-neutral-500 font-mono"
                    >PLATFORM</span
                  >
                </div>
                <h3
                  class="mt-4 text-lg font-bold text-neutral-800 group-hover:text-primary transition"
                >
                  平台字典
                  <span
                    class="text-xs font-normal text-neutral-400 font-mono block"
                    >vehicle_platforms</span
                  >
                </h3>
                <p class="mt-1.5 text-xs text-neutral-500 line-clamp-2">
                  涵盖纯电、插混等不同驱动模式和轴距区间的车身基础架构平台。
                </p>
              </div>
              <div
                class="mt-6 border-t border-neutral-100 pt-4 flex items-center justify-between text-xs"
              >
                <span class="text-neutral-400 font-medium"
                  >轴距:
                  <span class="font-mono text-neutral-600"
                    >2.6m - 3.3m</span
                  ></span
                >
                <span
                  class="text-primary font-bold group-hover:translate-x-1 transition-transform"
                >
                  →
                </span>
              </div>
            </div>

            <!-- 工艺区域 (Bento Card 3) -->
            <div
              @click="openDrawer('process_areas')"
              class="group cursor-pointer rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/30 flex flex-col justify-between"
            >
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-2xl">🏭</span>
                  <span
                    class="rounded-full bg-neutral-100 px-2.5 py-0.5 text-[10px] font-bold text-neutral-500 font-mono"
                    >PROCESS</span
                  >
                </div>
                <h3
                  class="mt-4 text-lg font-bold text-neutral-800 group-hover:text-primary transition"
                >
                  工艺区域字典
                  <span
                    class="text-xs font-normal text-neutral-400 font-mono block"
                    >process_areas</span
                  >
                </h3>
                <p class="mt-1.5 text-xs text-neutral-500 line-clamp-2">
                  车间喷涂、前处理、电泳以及烘干区段，规定标准运行温度区间与区域主管。
                </p>
              </div>
              <div
                class="mt-6 border-t border-neutral-100 pt-4 flex items-center justify-between text-xs"
              >
                <span class="text-neutral-400 font-medium"
                  >包含:
                  <span class="font-mono text-neutral-600"
                    >PRE, PVC, BC, CC...</span
                  ></span
                >
                <span
                  class="text-primary font-bold group-hover:translate-x-1 transition-transform"
                >
                  →
                </span>
              </div>
            </div>

            <!-- 车型字典 (Bento Card 4) -->
            <div
              @click="openDrawer('vehicle_body_types')"
              class="group cursor-pointer rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/30 flex flex-col justify-between"
            >
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-2xl">🚗</span>
                  <span
                    class="rounded-full bg-neutral-100 px-2.5 py-0.5 text-[10px] font-bold text-neutral-500 font-mono"
                    >BODY</span
                  >
                </div>
                <h3
                  class="mt-4 text-lg font-bold text-neutral-800 group-hover:text-primary transition"
                >
                  车型字典
                  <span
                    class="text-xs font-normal text-neutral-400 font-mono block"
                    >vehicle_body_types</span
                  >
                </h3>
                <p class="mt-1.5 text-xs text-neutral-500 line-clamp-2">
                  轿车、SUV、MPV等不同外轮廓尺寸的数据集，包含长度及高宽。
                </p>
              </div>
              <div
                class="mt-6 border-t border-neutral-100 pt-4 flex items-center justify-between text-xs"
              >
                <span class="text-neutral-400 font-medium"
                  >参数:
                  <span class="font-mono text-neutral-600"
                    >SEDAN, SUV...</span
                  ></span
                >
                <span
                  class="text-primary font-bold group-hover:translate-x-1 transition-transform"
                >
                  →
                </span>
              </div>
            </div>

            <!-- 颜色字典 (Bento Card 5) -->
            <div
              @click="openDrawer('vehicle_color_codes')"
              class="group cursor-pointer rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/30 flex flex-col justify-between"
            >
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-2xl">🎨</span>
                  <span
                    class="rounded-full bg-neutral-100 px-2.5 py-0.5 text-[10px] font-bold text-neutral-500 font-mono"
                    >COLOR</span
                  >
                </div>
                <h3
                  class="mt-4 text-lg font-bold text-neutral-800 group-hover:text-primary transition"
                >
                  颜色颜色字典
                  <span
                    class="text-xs font-normal text-neutral-400 font-mono block"
                    >vehicle_color_codes</span
                  >
                </h3>
                <p class="mt-1.5 text-xs text-neutral-500 line-clamp-2">
                  涂装油漆编码对照表，含珍珠白、极光黑、钛金灰等珍珠漆与金属漆色值。
                </p>
              </div>
              <div
                class="mt-6 border-t border-neutral-100 pt-4 flex items-center justify-between text-xs"
              >
                <span class="text-neutral-400 font-medium"
                  >色组:
                  <span class="font-mono text-neutral-600"
                    >黑/白/灰/红/蓝</span
                  ></span
                >
                <span
                  class="text-primary font-bold group-hover:translate-x-1 transition-transform"
                >
                  →
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 侧拉毛玻璃抽屉 (Slide-over Drawer) -->
    <Transition name="slide-over">
      <div v-if="drawerOpen" class="fixed inset-0 z-50 overflow-hidden">
        <!-- 抽屉暗色背景遮罩 -->
        <div
          class="absolute inset-0 bg-neutral-900/35 backdrop-blur-[2px] transition-opacity duration-300"
          @click="closeDrawer"
        ></div>

        <div class="absolute inset-y-0 right-0 pl-10 max-w-full flex">
          <div
            class="w-screen max-w-3xl flex flex-col border-l border-neutral-200/50 bg-white/95 shadow-2xl backdrop-blur-xl"
          >
            <!-- 抽屉头部 -->
            <div
              class="px-6 py-5 border-b border-neutral-200/80 flex items-center justify-between bg-neutral-50/50 shrink-0"
            >
              <div class="flex items-center gap-2">
                <span class="text-xl">📚</span>
                <h2 class="text-lg font-black text-neutral-800">
                  {{ TABLE_LABELS[activeTable || ""] }}
                </h2>
              </div>
              <button
                @click="closeDrawer"
                class="rounded-xl border border-neutral-200 p-2 text-neutral-500 transition hover:bg-neutral-100 hover:text-neutral-700"
              >
                <svg
                  class="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <!-- 抽屉主要数据展示区 -->
            <div class="flex-1 overflow-y-auto p-4 min-h-0 bg-white">
              <div v-if="loading" class="flex h-64 items-center justify-center">
                <div class="flex flex-col items-center gap-2">
                  <svg
                    class="h-8 w-8 animate-spin text-primary"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      class="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      stroke-width="4"
                    ></circle>
                    <path
                      class="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  <p class="text-xs text-neutral-400 font-medium">
                    获取数据中...
                  </p>
                </div>
              </div>

              <div
                v-else-if="error"
                class="flex h-64 items-center justify-center p-6 text-center"
              >
                <div>
                  <p class="text-sm font-semibold text-red-600">{{ error }}</p>
                  <button
                    class="mt-4 rounded-xl border border-neutral-200 bg-white px-4 py-2 text-xs font-semibold text-neutral-600"
                    @click="fetchTableData"
                  >
                    重试
                  </button>
                </div>
              </div>

              <DimensionTable
                v-else-if="tableData"
                :title="TABLE_LABELS[tableData.table_name]"
                :tableName="tableData.table_name"
                :columns="tableData.columns"
                :rows="tableData.rows"
                @dblclick-cell="$emit('dblclick-cell', $event)"
              />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import {
  getDimensionTableApi,
  type DimensionTableData,
} from "../api/dimensions";
import DimensionTable from "./DimensionTable.vue";

defineProps<{
  isSidebarOpen: boolean;
  showBento: boolean;
}>();

defineEmits<{
  closeSidebar: [];
  "toggle-bento": [];
  "dblclick-cell": [value: string];
}>();

const TABLE_LABELS: Record<string, string> = {
  carrier_types: "载体类型字典",
  process_areas: "工艺区域字典",
  vehicle_body_types: "车型字典",
  vehicle_color_codes: "颜色字典",
  vehicle_platforms: "平台字典",
};

const drawerOpen = ref(false);
const activeTable = ref<string | null>(null);
const tableData = ref<DimensionTableData | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

async function openDrawer(tableName: string) {
  activeTable.value = tableName;
  drawerOpen.value = true;
  await fetchTableData();
}

function closeDrawer() {
  drawerOpen.value = false;
  activeTable.value = null;
  tableData.value = null;
}

async function fetchTableData() {
  if (!activeTable.value) return;
  loading.value = true;
  error.value = null;
  try {
    tableData.value = await getDimensionTableApi(activeTable.value);
  } catch (e: any) {
    error.value = e.message || "数据加载失败，请稍后重试";
    tableData.value = null;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
/* Slide-over Transition */
.slide-over-enter-active,
.slide-over-leave-active {
  transition: all 0.3s ease-out;
}

.slide-over-enter-from,
.slide-over-leave-to {
  opacity: 0;
}

.slide-over-enter-from .absolute.right-0,
.slide-over-leave-to .absolute.right-0 {
  transform: translateX(100%);
}

.slide-over-enter-to .absolute.right-0,
.slide-over-leave-to .absolute.right-0 {
  transform: translateX(0);
}
</style>
