import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  chatWithMemory,
  clearHistory,
  getHealth,
  getHistory,
  HealthCheckError,
  historyErrorKindOf,
  HistoryFormatError,
  HistoryRequestError,
  HistoryUnavailableError,
  isClearHistorySuccess,
  normalizeHistoryPayload
} from "@/api/chat"

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn()
}))

vi.mock("axios", () => ({
  default: { create: () => ({ get: mockGet, post: mockPost }) }
}))

function httpError(status: number, data?: unknown) {
  return Object.assign(new Error(`Request failed with status code ${status}`), {
    isAxiosError: true,
    response: { status, data }
  })
}

const validRawItem = { id: "a", question: "问", answer: "答", time: "2026-09-29T10:00:00" }

beforeEach(() => {
  mockGet.mockReset()
  mockPost.mockReset()
})

describe("getHistory 结构兼容与校验", () => {
  it("兼容裸数组", async () => {
    mockGet.mockResolvedValue({ data: [validRawItem] })
    const { items } = await getHistory()
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ id: "a", question: "问", answer: "答", time: "2026-09-29T10:00:00" })
    expect(mockGet).toHaveBeenCalledWith("/get_history")
  })

  it("兼容 { items: [] }", async () => {
    mockGet.mockResolvedValue({ data: { items: [validRawItem] } })
    const { items } = await getHistory()
    expect(items).toHaveLength(1)
  })

  it("兼容 { history: [] }，且两种键同时存在时保持 history 优先（与旧实现一致）", async () => {
    mockGet.mockResolvedValue({ data: { history: [validRawItem] } })
    expect((await getHistory()).items).toHaveLength(1)

    mockGet.mockResolvedValue({ data: { items: [], history: [validRawItem] } })
    expect((await getHistory()).items).toHaveLength(1)
  })

  it("空数组是成功空历史", async () => {
    mockGet.mockResolvedValue({ data: [] })
    await expect(getHistory()).resolves.toEqual({ items: [] })
  })

  it("非法容器结构抛 HistoryFormatError，不静默当空", async () => {
    for (const payload of [{}, null, "ok", 3, { items: "x" }, { history: {} }]) {
      mockGet.mockResolvedValue({ data: payload })
      await expect(getHistory()).rejects.toBeInstanceOf(HistoryFormatError)
      await expect(getHistory()).rejects.toMatchObject({ kind: "format" })
    }
  })

  it("条目缺少 question / answer 或类型错误时整体拒绝", async () => {
    const badItems = [
      { answer: "答" },
      { question: "问" },
      { question: 1, answer: "答" },
      { question: "问", answer: null },
      "not-an-object",
      { question: "问", answer: "答", id: {} },
      { question: "问", answer: "答", time: [] }
    ]
    for (const bad of badItems) {
      mockGet.mockResolvedValue({ data: { items: [bad] } })
      await expect(getHistory()).rejects.toBeInstanceOf(HistoryFormatError)
    }
    // 合法条目数量为 0 时不受影响
    mockGet.mockResolvedValue({ data: { items: [] } })
    await expect(getHistory()).resolves.toEqual({ items: [] })
  })

  it("time 为数字时转成 ISO 字符串，非法数字被拒绝", () => {
    const [item] = normalizeHistoryPayload([{ id: "t", question: "问", answer: "答", time: 1727000000000 }])
    expect(typeof item.time).toBe("string")
    expect(Number.isNaN(new Date(item.time as string).getTime())).toBe(false)
    expect(() => normalizeHistoryPayload([{ id: "t", question: "问", answer: "答", time: Number.NaN }])).toThrow(HistoryFormatError)
  })

  it("id 为数字时转成字符串", () => {
    const [item] = normalizeHistoryPayload([{ id: 7, question: "问", answer: "答" }])
    expect(item.id).toBe("7")
  })

  it("缺失 id 生成按序号的展示 id；key 由 id 与序号组成且稳定", () => {
    const items = normalizeHistoryPayload([
      { question: "问一", answer: "答一" },
      { question: "问二", answer: "答二" }
    ])
    expect(items.map(item => item.id)).toEqual(["history-1", "history-2"])
    expect(items.map(item => item.key)).toEqual([JSON.stringify(["history-1", 0]), JSON.stringify(["history-2", 1])])
    expect(new Set(items.map(item => item.key)).size).toBe(2)
  })

  it("重复 id、带 # 后缀 id、缺失 id 与真实 id 撞名时 key 均不冲突", () => {
    const items = normalizeHistoryPayload([
      { id: "dup", question: "q0", answer: "a0" },
      { id: "dup", question: "q1", answer: "a1" },
      { id: "dup#2", question: "q2", answer: "a2" },
      { question: "q3", answer: "a3" },
      { id: "history-4", question: "q4", answer: "a4" }
    ])
    const keys = items.map(item => item.key)
    expect(new Set(keys).size).toBe(5)
    expect(keys[2]).toBe(JSON.stringify(["dup#2", 2]))
  })

  it("404 / 501 归类为未开放，其它状态与网络错误归类为请求失败", async () => {
    mockGet.mockRejectedValue(httpError(404))
    await expect(getHistory()).rejects.toBeInstanceOf(HistoryUnavailableError)
    await expect(getHistory()).rejects.toMatchObject({ kind: "unavailable" })

    mockGet.mockRejectedValue(httpError(501))
    await expect(getHistory()).rejects.toBeInstanceOf(HistoryUnavailableError)

    mockGet.mockRejectedValue(httpError(500))
    await expect(getHistory()).rejects.toMatchObject({ kind: "request", status: 500 })

    mockGet.mockRejectedValue(new Error("Network Error"))
    await expect(getHistory()).rejects.toBeInstanceOf(HistoryRequestError)
  })

  it("historyErrorKindOf 分类稳定", () => {
    expect(historyErrorKindOf(new HistoryUnavailableError())).toBe("unavailable")
    expect(historyErrorKindOf(new HistoryFormatError())).toBe("format")
    expect(historyErrorKindOf(new HistoryRequestError())).toBe("request")
    expect(historyErrorKindOf(new Error("x"))).toBe("request")
  })
})

describe("clearHistory 成功契约", () => {
  it("显式失败响应被拒绝，不作为清空成功", async () => {
    for (const data of [{ success: false }, { ok: false }, { status: "error" }, { status: "FAILED" }, { status: "fail" }]) {
      mockPost.mockResolvedValue({ data })
      await expect(clearHistory()).rejects.toBeInstanceOf(HistoryRequestError)
    }
  })

  it("2xx 且无失败标记视为成功（含 204 空响应与 { success: true }）", async () => {
    for (const data of ["", undefined, {}, { success: true }, { status: "ok" }]) {
      mockPost.mockResolvedValue({ data })
      await expect(clearHistory()).resolves.toBe(data)
    }
    expect(isClearHistorySuccess({ success: false })).toBe(false)
    expect(isClearHistorySuccess({ status: "error" })).toBe(false)
    expect(isClearHistorySuccess({ success: true })).toBe(true)
  })

  it("404 / 501 归类为未开放，500 归类为请求失败", async () => {
    mockPost.mockRejectedValue(httpError(404))
    await expect(clearHistory()).rejects.toBeInstanceOf(HistoryUnavailableError)
    mockPost.mockRejectedValue(httpError(500))
    await expect(clearHistory()).rejects.toMatchObject({ kind: "request", status: 500 })
  })
})

describe("getHealth", () => {
  const raw = {
    status: "ok",
    checks: ["process", "config"],
    external_dependencies_checked: false,
    retrieval_mode: "keyword",
    model: "qwen3.5:4b",
    rag_service_ready: true,
    note: "仅报告进程与配置，不检测 Ollama 与向量库是否可用"
  }

  it("解析后端健康响应字段", async () => {
    mockGet.mockResolvedValue({ data: raw })
    await expect(getHealth()).resolves.toEqual({
      status: "ok",
      retrievalMode: "keyword",
      model: "qwen3.5:4b",
      ragServiceReady: true,
      externalDependenciesChecked: false,
      note: raw.note
    })
    expect(mockGet).toHaveBeenCalledWith("/health")
  })

  it("缺少可选字段时降级，缺少 status 视为失败", async () => {
    mockGet.mockResolvedValue({ data: { status: "ok" } })
    await expect(getHealth()).resolves.toMatchObject({ retrievalMode: "unknown", model: "", ragServiceReady: null })

    mockGet.mockResolvedValue({ data: {} })
    await expect(getHealth()).rejects.toBeInstanceOf(HealthCheckError)
    mockGet.mockResolvedValue({ data: null })
    await expect(getHealth()).rejects.toBeInstanceOf(HealthCheckError)
  })

  it("网络/服务错误抛 HealthCheckError", async () => {
    mockGet.mockRejectedValue(new Error("Network Error"))
    await expect(getHealth()).rejects.toBeInstanceOf(HealthCheckError)
  })
})

describe("chatWithMemory 回落行为无回归", () => {
  it("第一个接口失败（任意失败）后回落到 /chat 并返回答案", async () => {
    mockPost
      .mockRejectedValueOnce(httpError(500))
      .mockResolvedValueOnce({ data: { answer: "来自 /chat" } })
    await expect(chatWithMemory("问题")).resolves.toEqual({ answer: "来自 /chat" })
    expect(mockPost.mock.calls.map(call => call[0])).toEqual(["/chat_with_memory", "/chat"])
  })

  it("字符串响应与 response 字段仍被归一化", async () => {
    mockPost.mockRejectedValueOnce(httpError(404)).mockResolvedValueOnce({ data: "纯文本回答" })
    await expect(chatWithMemory("问题")).resolves.toEqual({ answer: "纯文本回答" })

    mockPost.mockRejectedValueOnce(httpError(404)).mockResolvedValueOnce({ data: { response: "resp" } })
    await expect(chatWithMemory("问题")).resolves.toEqual({ answer: "resp" })
  })

  it("两次请求都失败时抛错", async () => {
    mockPost.mockRejectedValue(httpError(503))
    await expect(chatWithMemory("问题")).rejects.toBeTruthy()
    expect(mockPost).toHaveBeenCalledTimes(2)
  })
})
