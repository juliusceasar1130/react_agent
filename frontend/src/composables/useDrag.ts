// 可拖拽手势 composable — 支持鼠标与触摸事件

import { ref, onUnmounted } from 'vue'

interface UseDragOptions {
  /** 触发拖拽的最小位移（像素），默认 5px */
  threshold?: number
}

export function useDrag(options: UseDragOptions = {}) {
  const threshold = options.threshold ?? 5

  const position = ref({ x: 0, y: 0 })
  const isDragging = ref(false)
  const hasMoved = ref(false)

  let startPos = { x: 0, y: 0 }
  let initialOffset = { x: 0, y: 0 }

  function onPointerDown(e: MouseEvent | TouchEvent) {
    // 仅响应鼠标左键
    if ('button' in e && e.button !== 0) return
    e.preventDefault()

    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY

    isDragging.value = true
    hasMoved.value = false
    startPos = { x: clientX, y: clientY }
    initialOffset = { ...position.value }

    window.addEventListener('mousemove', onPointerMove)
    window.addEventListener('mouseup', onPointerUp)
    window.addEventListener('touchmove', onPointerMove, { passive: false })
    window.addEventListener('touchend', onPointerUp)
  }

  function onPointerMove(e: MouseEvent | TouchEvent) {
    if (!isDragging.value) return
    e.preventDefault()

    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY

    const dx = clientX - startPos.x
    const dy = clientY - startPos.y

    if (Math.abs(dx) > threshold || Math.abs(dy) > threshold) {
      hasMoved.value = true
    }

    position.value = {
      x: initialOffset.x + dx,
      y: initialOffset.y + dy,
    }
  }

  function onPointerUp() {
    isDragging.value = false
    window.removeEventListener('mousemove', onPointerMove)
    window.removeEventListener('mouseup', onPointerUp)
    window.removeEventListener('touchmove', onPointerMove)
    window.removeEventListener('touchend', onPointerUp)
  }

  // 重置位置
  function reset(x = 0, y = 0) {
    position.value = { x, y }
    hasMoved.value = false
    isDragging.value = false
  }

  // 组件卸载时自动清理
  onUnmounted(() => {
    isDragging.value = false
    window.removeEventListener('mousemove', onPointerMove)
    window.removeEventListener('mouseup', onPointerUp)
    window.removeEventListener('touchmove', onPointerMove)
    window.removeEventListener('touchend', onPointerUp)
  })

  return {
    position,
    isDragging,
    hasMoved,
    onPointerDown,
    reset,
  }
}