# 聊天问题刻度线导航设计规格 (Question Rail Design Spec)

> 日期: 2026-08-23  
> 状态: Approved with Suggestions (已通过 CC 审查并采纳优化建议)  
> 领域: Frontend / Chat UX  

## 1. 目标与背景 (Goal & Motivation)

### 1.1 背景
在多轮数据分析与复杂问答场景下，对话记录通常较长。用户需要频繁上下滑动以寻找先前的提问，难以快速掌握全局脉络和实现上下文间的快速穿梭。

### 1.2 目标
参考主流 AI 对话产品（如 Kimi）的刻度线导览设计：
- **常态极简刻度线**：在聊天区域右侧展示轻量竖向短横线（刻度线），不遮挡正文与图表卡片；
- **悬停毛玻璃卡片**：鼠标悬停在刻度线区域时，平滑展开包含历史提问概览的毛玻璃卡片（左侧截断文本，右侧对应刻度线）；
- **平滑定位与落点微光**：点击问题项即可平滑滚动至对应消息气泡，并触发 1.2 秒的呼吸微光高亮；
- **双向视口滚动感知**：监听页面滚动，动态点亮当前视口可见问题对应的刻度线。

---

## 2. 总体架构与模块划分 (Architecture)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ MessageList.vue (滚动容器 & 消息流)                                           │
│  ├── useScrollSpy.ts (滚动监听、rAF节流、视口相对定位计算、ResizeObserver)     │
│  │                                                                          │
│  ├── MessageItem.vue (id="msg-{id}", :class="{ 'highlight-pulse': ... }")  │
│  │   - 消息 1 (User)                                                        │
│  │   - 消息 2 (Assistant / Reasoning / Artifacts)                          │
│  │   - 消息 3 (User)                                                        │
│  │                                                                          │
│  └── QuestionRail.vue (右侧独立浮层组件, fixed/absolute z-30)              │
│      ├── Collapsed State: 极简刻度短横线                                    │
│      └── Expanded State: 毛玻璃浮层卡片 (单行截断文本 + 刻度线)             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 模块职责与接口契约

1. **`useScrollSpy.ts` [NEW Composable]**：
   - 封装滚动监听、`requestAnimationFrame` 节流与组件卸载时的资源释放（`cancelAnimationFrame`）；
   - 使用 `getBoundingClientRect()` 精准计算元素相对于滚动容器视口的相对位移；
   - 监听 `ResizeObserver`，在消息流式输出、图表展开导致高度变化时自动重新校准激活项；
   - 暴露 `activeId`、`scrollToMessage(messageId)` 等核心响应式状态与定位方法。

2. **`QuestionRail.vue` [NEW Component]**：
   - 接收 `userQuestions`、`activeId`、`loading` 等 props，派发 `select(id)` 事件；
   - 管理卡片的展开/收起过渡动画（Hover Transition）；
   - 支持键盘导航（上下键聚焦、Enter 跳转）与无障碍属性（`role="navigation"`、`aria-label="问题导航"`）；
   - 使用 `v-memo` 优化长对话下的列表渲染性能。

3. **`MessageList.vue` [MODIFIED]**：
   - 挂载 `QuestionRail` 并接入 `useScrollSpy`；
   - 在 `defineExpose` 中显式暴露 `scrollToBottom` 与 `scrollToMessage`；
   - 配合 `currentSessionId` 绑定 key 或重置逻辑，杜绝会话切换竞态。

4. **`MessageItem.vue` [MODIFIED]**：
   - 用户消息节点显式绑定 DOM 标识（`id="msg-${message.id}"`）；
   - 增加微光呼吸动画样式 `.highlight-pulse`。

---

## 3. 详细设计与交互规范 (Detailed Design)

### 3.1 状态机与视觉表现

| 状态 | 触发条件 | 视觉表现与样式 |
| :--- | :--- | :--- |
| **隐藏态 (Hidden)** | `userQuestions.length < 2` 或 `loading === true` 或 移动端 (`< 768px`) | 组件不渲染 (`v-if="false"` 或 `hidden md:flex`) |
| **收起常态 (Collapsed)** | 默认状态，鼠标未进入热区 | 一列垂直居中的刻度线；普通项：宽 16px、高 2px、`bg-neutral-300`；当前视口激活项：宽 20px、高 2px、`bg-neutral-900` |
| **展开态 (Expanded)** | 鼠标移入刻度线热区 (`mouseenter`) | 平滑向左展开毛玻璃卡片（宽 260px~300px，`bg-white/95 backdrop-blur-xl rounded-2xl shadow-xl border border-neutral-200/80`），左侧显示单行截断文本，右侧对齐刻度线 |
| **项悬浮态 (Item Hover)** | 鼠标在展开卡片内划过某一行 | 该行背景变为浅灰圆角胶囊 (`bg-neutral-100/90 rounded-lg`)，文字加深，对应刻度线变黑 |

### 3.2 精准视口计算与滚动算法

```ts
// 使用 getBoundingClientRect 避免 offsetParent 嵌套断裂问题
const ACTIVATION_OFFSET_TOP = 120 // 顶部判定阈值（单位：px，避开 Header 遮挡）

function calculateActiveMessage() {
  if (!containerEl) return
  const containerRect = containerEl.getBoundingClientRect()
  
  // 底部判定：若已触底，强制激活最后一条用户问题
  const isBottom = containerEl.scrollHeight - containerEl.scrollTop - containerEl.clientHeight < 40
  if (isBottom && userQuestions.value.length > 0) {
    activeId.value = userQuestions.value[userQuestions.value.length - 1].id
    return
  }

  let currentActive = null
  for (const q of userQuestions.value) {
    const el = document.getElementById(`msg-${q.id}`)
    if (!el) continue
    const rect = el.getBoundingClientRect()
    const relativeTop = rect.top - containerRect.top
    if (relativeTop <= ACTIVATION_OFFSET_TOP) {
      currentActive = q.id
    } else {
      break
    }
  }
  activeId.value = currentActive || userQuestions.value[0]?.id || null
}
```

### 3.3 点击定位与微光反馈 (Click-to-Locate)

```ts
function scrollToMessage(messageId: string) {
  const el = document.getElementById(`msg-${messageId}`)
  if (!el || !containerEl) return

  const containerRect = containerEl.getBoundingClientRect()
  const elRect = el.getBoundingClientRect()
  const scrollOffset = elRect.top - containerRect.top + containerEl.scrollTop - 16

  containerEl.scrollTo({
    top: Math.max(0, scrollOffset),
    behavior: 'smooth'
  })

  // 触发气泡微光呼吸反馈
  el.classList.add('highlight-pulse')
  setTimeout(() => {
    el.classList.remove('highlight-pulse')
  }, 1200)
}
```

---

## 4. 边界条件与健壮性保障 (Robustness)

1. **会话切换竞态防护**：在切换 `currentSessionId` 时，立即重置 `activeId` 并清空状态，在 `fetchMessages` 完成且 `loading === false` 后再计算。
2. **多行与超长提问**：提问文本在展示时过滤多余换行符、单行展示，超出使用 CSS `truncate`。
3. **内容高度动态变动**：引入 `ResizeObserver` 监听聊天内容区域，在流式输出、图表卡片渲染完成后自动校准激活状态。
4. **生命周期清理**：在 `onUnmounted` 中显式 `cancelAnimationFrame`、注销 `scroll` 事件监听和断开 `ResizeObserver`，杜绝内存泄漏。

---

## 5. 验证与交付计划 (Verification)

1. **功能与渲染验证**：
   - 验证单条提问及欢迎页时不出现刻度线；≥ 2 条提问时自动出现并居中展示；
   - 验证悬停平滑展开毛玻璃卡片、移出平滑收起；
   - 验证点击问题平滑定位与 1.2s 微光呼吸动效；
   - 验证页面滚动时刻度线实时准确点亮。
2. **边缘与性能验证**：
   - 验证流式生成过程中刻度线稳定无抖动；
   - 验证会话切换无残影与旧数据闪烁；
   - 验证屏幕宽度 `< 768px` 自动隐藏。
