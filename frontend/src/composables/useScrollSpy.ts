// 2026-08-23 Asia/Shanghai - 滚动视口监听与消息定位 Composable
import { ref, watch, nextTick, onMounted, onUnmounted, type Ref } from 'vue'

export interface UserQuestionItem {
  id: string
  content: string
  index: number
}

const ACTIVATION_OFFSET_TOP = 120 // 视口判定顶部偏移阈值 (px)，避开顶部 Header
const BOTTOM_THRESHOLD = 40       // 滚动触底判定阈值 (px)

export function useScrollSpy(
  containerRef: Ref<HTMLElement | null>,
  userQuestions: Ref<UserQuestionItem[]>
) {
  const activeId = ref<string | null>(null)
  let rafId: number | null = null
  let resizeObserver: ResizeObserver | null = null
  let pulseTimer: ReturnType<typeof setTimeout> | null = null

  const calculateActiveMessage = () => {
    const container = containerRef.value
    if (!container || userQuestions.value.length === 0) {
      activeId.value = null
      return
    }

    const containerRect = container.getBoundingClientRect()
    // 底部判定：若已滚动至最底部，强制将最后一条用户提问标记为激活项
    const isBottom = container.scrollHeight - container.scrollTop - container.clientHeight < BOTTOM_THRESHOLD

    if (isBottom) {
      activeId.value = userQuestions.value[userQuestions.value.length - 1].id
      return
    }

    let matchedId: string | null = null
    for (const q of userQuestions.value) {
      const el = document.getElementById(`msg-${q.id}`)
      if (!el) continue
      const rect = el.getBoundingClientRect()
      const relativeTop = rect.top - containerRect.top
      if (relativeTop <= ACTIVATION_OFFSET_TOP) {
        matchedId = q.id
      } else {
        break
      }
    }

    activeId.value = matchedId || userQuestions.value[0]?.id || null
  }

  const handleScroll = () => {
    if (rafId !== null) cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      calculateActiveMessage()
      rafId = null
    })
  }

  const scrollToMessage = (messageId: string) => {
    const container = containerRef.value
    const el = document.getElementById(`msg-${messageId}`)
    if (!container || !el) return

    const containerRect = container.getBoundingClientRect()
    const elRect = el.getBoundingClientRect()
    const targetScrollTop = elRect.top - containerRect.top + container.scrollTop - 16

    container.scrollTo({
      top: Math.max(0, targetScrollTop),
      behavior: 'smooth'
    })

    // 触发气泡微光呼吸反馈
    if (pulseTimer) clearTimeout(pulseTimer)
    el.classList.remove('highlight-pulse')
    void el.offsetWidth // 强制重绘以重新触发动画
    el.classList.add('highlight-pulse')
    pulseTimer = setTimeout(() => {
      el.classList.remove('highlight-pulse')
      pulseTimer = null
    }, 1200)
  }

  watch(userQuestions, () => {
    nextTick(() => {
      calculateActiveMessage()
    })
  })

  onMounted(() => {
    const container = containerRef.value
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true })
      // 观察内部实际内容区域高度变化
      resizeObserver = new ResizeObserver(() => {
        handleScroll()
      })
      if (container.firstElementChild) {
        resizeObserver.observe(container.firstElementChild)
      } else {
        resizeObserver.observe(container)
      }
    }
  })

  onUnmounted(() => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (pulseTimer) {
      clearTimeout(pulseTimer)
      pulseTimer = null
    }
    const container = containerRef.value
    if (container) {
      container.removeEventListener('scroll', handleScroll)
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  })

  return {
    activeId,
    scrollToMessage,
    calculateActiveMessage
  }
}
