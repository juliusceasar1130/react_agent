<template>
  <div
    class="rounded-2xl border border-[#D8E2EE] bg-[#F6F9FC]/90 p-5 shadow-md backdrop-blur-xl transition-all duration-300"
    :class="[isSubmitted ? 'opacity-80 pointer-events-none' : '']"
  >
    <!-- Questions Panel -->
    <div class="space-y-6">
      <div v-for="(item, index) in questions" :key="index" class="space-y-3">
        <!-- Question Header Badge -->
        <div class="flex items-center gap-2">
          <span
            v-if="questions.length > 1"
            class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-blue-600 text-white shadow-sm"
          >
            问题 {{ index + 1 }} / {{ questions.length }}
          </span>
          <span
            v-if="item.header"
            class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100"
          >
            {{ item.header }}
          </span>
          <span
            v-if="item.options && item.options.length > 0"
            class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200"
          >
            {{ item.multiSelect ? '多选' : '单选' }}
          </span>
        </div>

        <!-- Question Title -->
        <h4 class="text-sm font-bold text-slate-800 leading-snug">
          {{ item.question }}
        </h4>

        <!-- Options Grid -->
        <div v-if="item.options && item.options.length > 0" class="grid grid-cols-1 gap-2.5">
          <div
            v-for="opt in item.options"
            :key="opt.label"
            @click="onOptionClick(item, opt.label)"
            class="group flex flex-col items-start p-3 rounded-xl border border-slate-200 bg-white/70 hover:border-blue-400 hover:bg-blue-50/20 cursor-pointer transition-all duration-200 shadow-sm"
            :class="[
              isOptionSelected(item, opt.label)
                ? 'border-blue-500 bg-blue-50/50 shadow-inner'
                : ''
            ]"
          >
            <div class="flex items-center gap-2.5 w-full">
              <!-- Radio/Checkbox circle -->
              <div
                class="flex items-center justify-center w-4 h-4 rounded-full border transition-all duration-200"
                :class="[
                  isOptionSelected(item, opt.label)
                    ? 'border-blue-500 bg-blue-500 text-white'
                    : 'border-slate-300 bg-white group-hover:border-slate-400'
                ]"
              >
                <div
                  v-if="isOptionSelected(item, opt.label)"
                  class="w-1.5 h-1.5 rounded-full bg-white"
                ></div>
              </div>
              <span
                class="text-xs font-semibold transition-colors duration-200"
                :class="[isOptionSelected(item, opt.label) ? 'text-blue-700' : 'text-slate-800']"
              >
                {{ opt.label }}
              </span>
            </div>
            <p
              v-if="opt.description"
              class="mt-1.5 pl-6-5 text-[11px] leading-relaxed text-slate-500 group-hover:text-slate-600"
            >
              {{ opt.description }}
            </p>
          </div>
        </div>

        <!-- Free Input Textarea -->
        <div class="mt-2.5 space-y-1.5">
          <label class="text-[11px] font-medium text-slate-500 pl-0.5">
            {{ item.options && item.options.length > 0 ? '补充参数 / 关联说明' : '请输入答案 / 说明' }}
          </label>
          <textarea
            v-model="customInputs[item.question]"
            @input="onTextAreaInput(item)"
            :disabled="isSubmitted"
            class="w-full text-xs rounded-xl border border-slate-200 bg-white/60 p-2.5 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 outline-none resize-none transition-all duration-200 placeholder:text-slate-400 shadow-inner"
            :placeholder="item.options && item.options.length > 0 ? '若包含混合提问（如需同时输入车身号/时间等参数），请在此处填写...' : '请在此输入您的回答...'"
            rows="2.5"
          ></textarea>
        </div>
      </div>

      <!-- Submit Panel -->
      <div class="pt-2 flex justify-end gap-2.5">
        <button
          v-if="!isSubmitted"
          @click="handleCancel"
          class="px-5 py-2 text-xs font-bold text-slate-500 bg-slate-100 hover:bg-slate-200 hover:text-slate-700 rounded-xl transition-all duration-200 border border-slate-200"
        >
          取消
        </button>
        <button
          @click="handleSubmit"
          :disabled="!canSubmit || isSubmitted"
          class="px-5 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed rounded-xl shadow-sm hover:shadow transition-all duration-200 flex items-center gap-1.5"
        >
          <span v-if="isSubmitted">已提交选择</span>
          <span v-else>确认并恢复生成</span>
          <!-- Spinner for loading when submitted -->
          <svg
            v-if="isSubmitted"
            class="animate-spin h-3 w-3 text-white"
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
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { QuestionItem } from '@/types'

interface Props {
  questions: QuestionItem[]
  isSubmitted?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSubmitted: false
})

const emit = defineEmits<{
  (e: 'submit', answers: Record<string, string | string[]>): void
}>()

// 存储用户选择： question -> label(单选为string，多选为string[])
const answers = ref<Record<string, string | string[]>>({})
// 存储用户自定义输入: question -> text
const customInputs = ref<Record<string, string>>({})

// 初始化 answers 结构
const initAnswers = () => {
  for (const item of props.questions) {
    if (item.multiSelect) {
      answers.value[item.question] = []
    } else {
      answers.value[item.question] = ''
    }
    customInputs.value[item.question] = ''
  }
}

// 监听 questions 改变以重新初始化
watch(() => props.questions, initAnswers, { immediate: true })

// 辅助方法：检查某个选项是否被选中
const isOptionSelected = (item: QuestionItem, label: string): boolean => {
  const ans = answers.value[item.question]
  if (item.multiSelect) {
    return Array.isArray(ans) && ans.includes(label)
  }
  return ans === label
}

// 选项点击事件：更新选项选中值，不再清空自定义输入
const onOptionClick = (item: QuestionItem, label: string) => {
  if (props.isSubmitted) return

  if (item.multiSelect) {
    const current = (answers.value[item.question] as string[]) || []
    if (current.includes(label)) {
      answers.value[item.question] = current.filter((x) => x !== label)
    } else {
      answers.value[item.question] = [...current, label]
    }
  } else {
    if (answers.value[item.question] === label) {
      answers.value[item.question] = ''
    } else {
      answers.value[item.question] = label
    }
  }
}

// 自定义框输入事件：不再清空选项选中值
const onTextAreaInput = (_item: QuestionItem) => {
  // 不做操作，保持选项和输入共存
}

// 表单提交完整性校验
const canSubmit = computed(() => {
  if (props.isSubmitted) return false
  return props.questions.every((item) => {
    const ans = answers.value[item.question]
    const custom = customInputs.value[item.question]
    if (custom && custom.trim()) return true

    if (!item.options || item.options.length === 0) {
      return false
    }

    if (item.multiSelect) {
      return Array.isArray(ans) && ans.length > 0
    }
    return typeof ans === 'string' && ans !== ''
  })
})

const handleCancel = () => {
  if (props.isSubmitted) return

  const payload: Record<string, string | string[]> = {}
  for (const item of props.questions) {
    payload[item.question] = '已取消'
  }
  emit('submit', payload)
}

const handleSubmit = () => {
  if (!canSubmit.value) return

  const payload: Record<string, string | string[]> = {}
  for (const item of props.questions) {
    const custom = customInputs.value[item.question] ? customInputs.value[item.question].trim() : ''
    const ans = answers.value[item.question]

    if (item.options && item.options.length > 0) {
      let selectedText = ''
      if (Array.isArray(ans)) {
        selectedText = ans.join(', ')
      } else {
        selectedText = ans || ''
      }

      if (selectedText && custom) {
        // 如果既选了选项，又填了输入，则拼接回传后端
        payload[item.question] = `${selectedText}; 关联输入: ${custom}`
      } else if (custom) {
        payload[item.question] = custom
      } else {
        payload[item.question] = ans
      }
    } else {
      // 纯文本输入
      payload[item.question] = custom
    }
  }
  emit('submit', payload)
}
</script>

<style scoped>
.pl-6-5 {
  padding-left: 1.625rem;
}
</style>
