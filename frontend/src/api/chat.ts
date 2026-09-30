import type { ChatResponse, HealthInfo, HistoryDisplayItem, NormalizedHistoryResponse } from "@/types/chat"
import axios from "axios"

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
  timeout: 20000
})

export async function chatWithMemory(message: string): Promise<ChatResponse> {
  try {
    const { data } = await service.post("/chat_with_memory", { message })
    return normalizeChatResponse(data)
  } catch {
    const { data } = await service.post("/chat", { message })
    return normalizeChatResponse(data)
  }
}

/** 历史相关错误分类：未开放（404 / 501）、请求失败（网络 / 其他状态码）、响应格式异常 */
export type HistoryErrorKind = "unavailable" | "request" | "format"

/** 历史接口尚未实现（404 / 501） */
export class HistoryUnavailableError extends Error {
  readonly kind: HistoryErrorKind = "unavailable"
  constructor(message = "历史记录暂未开放") {
    super(message)
    this.name = "HistoryUnavailableError"
  }
}

/** 网络异常或其它非 404 / 501 的失败响应 */
export class HistoryRequestError extends Error {
  readonly kind: HistoryErrorKind = "request"
  constructor(message = "历史记录请求失败", readonly status?: number) {
    super(message)
    this.name = "HistoryRequestError"
  }
}

/** 响应不是约定的 [] / {items: []} / {history: []}，或条目字段类型不合法 */
export class HistoryFormatError extends Error {
  readonly kind: HistoryErrorKind = "format"
  constructor(message = "历史记录数据格式异常") {
    super(message)
    this.name = "HistoryFormatError"
  }
}

export function historyErrorKindOf(error: unknown): HistoryErrorKind {
  if (error instanceof HistoryUnavailableError) return "unavailable"
  if (error instanceof HistoryFormatError) return "format"
  return "request"
}

/** 健康检查失败（网络异常或响应缺少 status 字段） */
export class HealthCheckError extends Error {
  constructor(message = "健康检查失败", readonly status?: number) {
    super(message)
    this.name = "HealthCheckError"
  }
}

/**
 * 读取历史记录。
 *
 * - 兼容 `[]`、`{items: []}`、`{history: []}` 三种结构（与旧实现的优先级一致：history 优先于 items）。
 * - 逐条校验 question / answer 必须为字符串，id / time 允许字符串或数字（缺省可选）。
 * - 结构或字段不合法时抛出 `HistoryFormatError`，不会静默当成空历史。
 * - 404 / 501 抛出 `HistoryUnavailableError`，其余失败抛出 `HistoryRequestError`。
 */
export async function getHistory(): Promise<NormalizedHistoryResponse> {
  let data: unknown
  try {
    ({ data } = await service.get("/get_history"))
  } catch (error) {
    throw toHistoryError(error)
  }
  return { items: normalizeHistoryPayload(data) }
}

/** 清空历史；404 / 501 同样按“未开放”处理，其它失败抛出 `HistoryRequestError` */
export async function clearHistory() {
  let data: unknown
  try {
    ({ data } = await service.post("/clear_history"))
  } catch (error) {
    throw toHistoryError(error, "清空历史请求失败")
  }
  if (!isClearHistorySuccess(data)) {
    // 服务明确拒绝删除时不能清空 UI，按失败抛出
    throw new HistoryRequestError("清空历史失败：服务返回了失败状态")
  }
  return data
}

/**
 * 清空历史的成功契约：HTTP 2xx，且响应体没有显式声明失败。
 *
 * - 显式失败：`success === false`、`ok === false`，或 `status` 为 error / failed / fail。
 * - 空响应体（204 或 axios 的空字符串）没有失败标记，视为成功。
 * - 建议 A 的实现返回 `{"success": true}`，见 docs/api.md。
 */
export function isClearHistorySuccess(data: unknown): boolean {
  if (!isRecord(data)) return true
  if (data.success === false || data.ok === false) return false
  if (typeof data.status === "string" && ["error", "failed", "fail"].includes(data.status.toLowerCase())) return false
  return true
}

/**
 * 读取后端健康状态。
 *
 * 只反映“进程在线 + 配置信息”，不探测大模型 / 向量库；`external_dependencies_checked`
 * 为 false 时不代表依赖可用。响应缺少 status 时按失败处理，不视为在线。
 */
export async function getHealth(): Promise<HealthInfo> {
  let data: unknown
  try {
    ({ data } = await service.get("/health"))
  } catch (error) {
    throw new HealthCheckError(error instanceof Error ? error.message : "健康检查失败", getHttpStatus(error))
  }
  if (!isRecord(data) || typeof data.status !== "string") {
    throw new HealthCheckError("健康检查响应格式异常")
  }
  return {
    status: data.status,
    retrievalMode: typeof data.retrieval_mode === "string" ? data.retrieval_mode : "unknown",
    model: typeof data.model === "string" ? data.model : "",
    ragServiceReady: typeof data.rag_service_ready === "boolean" ? data.rag_service_ready : null,
    externalDependenciesChecked: typeof data.external_dependencies_checked === "boolean" ? data.external_dependencies_checked : null,
    note: typeof data.note === "string" ? data.note : ""
  }
}

export function normalizeHistoryPayload(data: unknown): HistoryDisplayItem[] {
  const list = pickHistoryList(data)
  return list.map((raw, index) => {
    const item = normalizeHistoryItem(raw, index)
    // 展示 key = id + 数组序号：同一响应内一定唯一，覆盖 id 重复、缺失、本身带 "#" 后缀等情况。
    // 仅用于列表渲染；后端契约仍要求每条记录提供唯一 id，顺序变化时 key 会变化。
    return { ...item, key: JSON.stringify([item.id, index]) }
  })
}

function pickHistoryList(data: unknown): unknown[] {
  if (Array.isArray(data)) return data
  if (isRecord(data)) {
    if (Array.isArray(data.history)) return data.history
    if (Array.isArray(data.items)) return data.items
    throw new HistoryFormatError("历史接口响应缺少 items / history 数组")
  }
  throw new HistoryFormatError("历史接口响应不是约定的数组结构")
}

function normalizeHistoryItem(raw: unknown, index: number): Omit<HistoryDisplayItem, "key"> {
  if (!isRecord(raw)) {
    throw new HistoryFormatError(`第 ${index + 1} 条历史记录不是对象`)
  }
  const { id, question, answer, time } = raw
  if (typeof question !== "string") {
    throw new HistoryFormatError(`第 ${index + 1} 条历史记录缺少有效的 question`)
  }
  if (typeof answer !== "string") {
    throw new HistoryFormatError(`第 ${index + 1} 条历史记录缺少有效的 answer`)
  }

  let normalizedId: string
  if (id === undefined || id === null || id === "") {
    // 后端契约要求提供唯一 id；缺失时按数组序号生成展示用 id（顺序变化时会随之变化）
    normalizedId = `history-${index + 1}`
  } else if (typeof id === "string") {
    normalizedId = id
  } else if (typeof id === "number" && Number.isFinite(id)) {
    normalizedId = String(id)
  } else {
    throw new HistoryFormatError(`第 ${index + 1} 条历史记录的 id 类型不受支持`)
  }

  let normalizedTime: string | undefined
  if (time === undefined || time === null || time === "") {
    normalizedTime = undefined
  } else if (typeof time === "string") {
    normalizedTime = time
  } else if (typeof time === "number" && Number.isFinite(time)) {
    const date = new Date(time)
    if (Number.isNaN(date.getTime())) {
      throw new HistoryFormatError(`第 ${index + 1} 条历史记录的时间无效`)
    }
    normalizedTime = date.toISOString()
  } else {
    throw new HistoryFormatError(`第 ${index + 1} 条历史记录的时间类型不受支持`)
  }

  return { id: normalizedId, question, answer, time: normalizedTime }
}

function toHistoryError(error: unknown, fallbackMessage = "历史记录请求失败"): Error {
  if (error instanceof HistoryUnavailableError || error instanceof HistoryRequestError || error instanceof HistoryFormatError) {
    return error
  }
  const status = getHttpStatus(error)
  if (status === 404 || status === 501) return new HistoryUnavailableError()
  return new HistoryRequestError(error instanceof Error ? error.message : fallbackMessage, status)
}

function getHttpStatus(error: unknown): number | undefined {
  const status = (error as { response?: { status?: unknown } } | null | undefined)?.response?.status
  return typeof status === "number" ? status : undefined
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function normalizeChatResponse(data: any): ChatResponse {
  if (typeof data === "string") return { answer: data }
  return {
    answer: data?.answer || data?.response || data?.message || ""
  }
}
