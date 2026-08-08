// 竞态防护 — 用于 async 请求的 request ID 计数器
// 在快速切换（如切换会话、滚动加载）时，丢弃过期响应，防止旧请求覆盖新数据

export function useRequestGuard() {
  let requestId = 0

  /**
   * 生成下一个请求 ID 并递增计数器
   */
  function next(): number {
    return ++requestId
  }

  /**
   * 检查指定 ID 是否仍为最新
   */
  function isFresh(id: number): boolean {
    return id === requestId
  }

  return { next, isFresh }
}