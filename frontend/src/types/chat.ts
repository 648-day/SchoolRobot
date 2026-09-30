export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
}

export interface ChatResponse {
  answer: string
}

export interface HistoryItem {
  id: string
  question: string
  answer: string
  time?: string
}

export interface HistoryResponse {
  items: HistoryItem[]
}

/**
 * getHistory 规范化后的条目。
 *
 * `key` 由 id 与数组序号共同生成，仅用于列表渲染：同一响应内一定唯一（覆盖 id 重复、
 * 缺失、本身带 `#` 后缀等情况），顺序变化时 key 会变化。历史接口契约仍要求后端为
 * 每条记录提供唯一 id，详见 docs/api.md。
 */
export interface HistoryDisplayItem extends HistoryItem {
  key: string
}

/** getHistory 的返回：items 已完成结构校验与展示 key 分配 */
export interface NormalizedHistoryResponse {
  items: HistoryDisplayItem[]
}

/**
 * GET /health 的展示字段（个人中心只读展示服务连接与检索模式）。
 *
 * `ragServiceReady` 只是后端进程内的服务配置状态，**不能当作大模型 / 向量库就绪**。
 */
export interface HealthInfo {
  status: string
  retrievalMode: string
  model: string
  ragServiceReady: boolean | null
  externalDependenciesChecked: boolean | null
  note: string
}

export interface KnowledgeFeedItem {
  id: string
  category: string
  title: string
  summary: string
  date: string
}
