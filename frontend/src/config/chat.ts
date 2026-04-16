// 修改时间: 2026-03-27 22:12 Asia/Shanghai
// 主要修改内容:
// - 新增聊天前端展示相关运行时开关
// - 默认隐藏流式过程细节，仅在内部调试模式下显示

export const CHAT_DEBUG_STREAM = import.meta.env.VITE_CHAT_DEBUG_STREAM === 'true'
