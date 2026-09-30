import type { HealthInfo, HistoryDisplayItem, NormalizedHistoryResponse } from "@/types/chat"
import { flushPromises, mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { clearHistory, getHealth, getHistory, HistoryFormatError, HistoryRequestError, HistoryUnavailableError } from "@/api/chat"
import MePage from "@/pages/me/index.vue"

const { confirmMock, failToastMock, successToastMock } = vi.hoisted(() => ({
  confirmMock: vi.fn(),
  failToastMock: vi.fn(),
  successToastMock: vi.fn()
}))

vi.mock("vant", async (importOriginal) => {
  const actual = await importOriginal<typeof import("vant")>()
  return {
    ...actual,
    showConfirmDialog: confirmMock,
    showFailToast: failToastMock,
    showSuccessToast: successToastMock
  }
})

vi.mock("@/api/chat", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/chat")>()
  return {
    ...actual,
    getHistory: vi.fn(),
    clearHistory: vi.fn(),
    getHealth: vi.fn()
  }
})

const getHistoryMock = vi.mocked(getHistory)
const clearHistoryMock = vi.mocked(clearHistory)
const getHealthMock = vi.mocked(getHealth)

const SETTINGS_KEY = "mobvue-me-settings-key"

const HEALTHY: HealthInfo = {
  status: "ok",
  retrievalMode: "keyword",
  model: "qwen3.5:4b",
  ragServiceReady: true,
  externalDependenciesChecked: false,
  note: "仅报告进程与配置，不检测 Ollama 与向量库是否可用"
}

function buildItems(raw: Array<{ id?: string, question: string, answer: string, time?: string }>): HistoryDisplayItem[] {
  return raw.map((item, index) => {
    const id = item.id ?? `history-${index + 1}`
    return { id, question: item.question, answer: item.answer, time: item.time, key: JSON.stringify([id, index]) }
  })
}

function okHistory(items: HistoryDisplayItem[]): NormalizedHistoryResponse {
  return { items }
}

function deferred<T = unknown>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function testid(id: string) {
  return `[data-testid=${id}]`
}

async function mountPage() {
  const wrapper = mount(MePage)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  getHistoryMock.mockResolvedValue(okHistory([]))
  getHealthMock.mockResolvedValue(HEALTHY)
  clearHistoryMock.mockResolvedValue(undefined)
  confirmMock.mockResolvedValue("confirm")
})

describe("历史记录状态", () => {
  it("加载中显示 loading，刷新与清空均不可点", async () => {
    const slow = deferred<NormalizedHistoryResponse>()
    getHistoryMock.mockReturnValueOnce(slow.promise)
    const wrapper = mount(MePage)
    await flushPromises()

    expect(wrapper.find(testid("history-loading")).exists()).toBe(true)
    expect(wrapper.find(testid("history-unavailable")).exists()).toBe(false)
    expect(wrapper.find(testid("history-empty")).exists()).toBe(false)
    expect(wrapper.find(testid("history-refresh")).attributes("disabled")).toBeDefined()
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeDefined()

    slow.resolve(okHistory([]))
    await flushPromises()
    expect(wrapper.find(testid("history-loading")).exists()).toBe(false)
    expect(wrapper.find(testid("history-empty")).exists()).toBe(true)
  })

  it("成功且为空：显示空历史，清空不可点", async () => {
    const wrapper = await mountPage()
    expect(wrapper.find(testid("history-empty")).text()).toContain("暂无历史记录")
    expect(wrapper.find(testid("history-unavailable")).exists()).toBe(false)
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeDefined()
    expect(wrapper.find(testid("summary-history")).text()).toBe("0")
  })

  it("成功且有记录：渲染问答、数量，清空可点", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([
      { id: "1", question: "食堂几点开门？", answer: "早上 7 点。", time: "2026-09-29T08:00:00" },
      { id: "2", question: "图书馆怎么借书？", answer: "凭校园卡借阅。" }
    ])))
    const wrapper = await mountPage()

    const cards = wrapper.findAll(testid("history-card"))
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain("食堂几点开门？")
    expect(cards[0].text()).toContain("早上 7 点。")
    expect(wrapper.find(testid("summary-history")).text()).toBe("2")
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeUndefined()
  })

  it("404 / 501 显示未开放文案与重试，且不显示为空历史", async () => {
    getHistoryMock.mockRejectedValueOnce(new HistoryUnavailableError())
    const wrapper = await mountPage()

    expect(wrapper.find(testid("history-unavailable")).text()).toContain("历史记录暂未开放，当前问答暂不保存历史。")
    expect(wrapper.find(testid("history-empty")).exists()).toBe(false)
    expect(wrapper.find(testid("history-retry")).exists()).toBe(true)
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeDefined()
  })

  it("网络 / 服务错误显示加载失败与重试，且不显示为空历史", async () => {
    getHistoryMock.mockRejectedValueOnce(new HistoryRequestError("boom", 500))
    const wrapper = await mountPage()

    expect(wrapper.find(testid("history-error")).text()).toContain("历史记录加载失败")
    expect(wrapper.find(testid("history-empty")).exists()).toBe(false)
    expect(wrapper.find(testid("history-retry")).exists()).toBe(true)
  })

  it("响应格式异常单独提示，不静默当空", async () => {
    getHistoryMock.mockRejectedValueOnce(new HistoryFormatError("缺字段"))
    const wrapper = await mountPage()

    expect(wrapper.find(testid("history-error")).text()).toContain("历史数据格式异常")
    expect(wrapper.find(testid("history-empty")).exists()).toBe(false)
  })

  it("点击重试后可从失败状态恢复", async () => {
    getHistoryMock
      .mockRejectedValueOnce(new HistoryUnavailableError())
      .mockResolvedValueOnce(okHistory(buildItems([{ id: "1", question: "问题", answer: "回答" }])))
    const wrapper = await mountPage()
    expect(wrapper.find(testid("history-unavailable")).exists()).toBe(true)

    await wrapper.find(testid("history-retry")).trigger("click")
    await flushPromises()
    expect(wrapper.find(testid("history-unavailable")).exists()).toBe(false)
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(1)
  })

  it("刷新失败保留旧记录并标注非最新，此时清空禁用", async () => {
    getHistoryMock
      .mockResolvedValueOnce(okHistory(buildItems([{ id: "1", question: "旧问题", answer: "旧回答" }])))
      .mockRejectedValueOnce(new HistoryRequestError("network"))
    const wrapper = await mountPage()
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(1)

    await wrapper.find(testid("history-refresh")).trigger("click")
    await flushPromises()
    expect(wrapper.find(testid("history-stale")).text()).toContain("可能不是最新")
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(1)
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeDefined()
    expect(wrapper.text()).not.toContain("已同步")
  })

  it("刷新进行中：显示刷新提示、清空禁用、旧记录保留且点击清空不发请求", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([{ id: "1", question: "旧问题", answer: "旧回答" }])))
    const wrapper = await mountPage()

    const slowRefresh = deferred<NormalizedHistoryResponse>()
    getHistoryMock.mockReturnValueOnce(slowRefresh.promise)
    await wrapper.find(testid("history-refresh")).trigger("click")

    expect(wrapper.find(testid("history-refreshing")).text()).toContain("正在刷新历史记录")
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(1)
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeDefined()

    await wrapper.find(testid("history-clear")).trigger("click")
    expect(clearHistoryMock).not.toHaveBeenCalled()

    slowRefresh.resolve(okHistory(buildItems([{ id: "1", question: "旧问题", answer: "旧回答" }])))
    await flushPromises()
    expect(wrapper.find(testid("history-refreshing")).exists()).toBe(false)
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeUndefined()
  })

  it("同一帧连点刷新：后发请求生效，先发旧响应不覆盖", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([{ id: "init", question: "初始", answer: "初始答" }])))
    const wrapper = await mountPage()

    const slowFirst = deferred<NormalizedHistoryResponse>()
    const fastSecond = deferred<NormalizedHistoryResponse>()
    getHistoryMock.mockReturnValueOnce(slowFirst.promise).mockReturnValueOnce(fastSecond.promise)

    const button = wrapper.find(testid("history-refresh"))
    const firstClick = button.trigger("click")
    const secondClick = button.trigger("click")
    await Promise.all([firstClick, secondClick])
    await flushPromises()
    expect(getHistoryMock).toHaveBeenCalledTimes(3) // 初次加载 + 同一帧的两次刷新

    fastSecond.resolve(okHistory(buildItems([{ id: "b", question: "第二次", answer: "后发结果" }])))
    await flushPromises()
    expect(wrapper.text()).toContain("后发结果")

    slowFirst.resolve(okHistory(buildItems([{ id: "a", question: "第一次", answer: "先发结果" }])))
    await flushPromises()
    expect(wrapper.text()).toContain("后发结果")
    expect(wrapper.text()).not.toContain("先发结果")
  })

  it("组件卸载后迟到的响应不再更新页面", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const slow = deferred<NormalizedHistoryResponse>()
    getHistoryMock.mockReturnValueOnce(slow.promise)
    const wrapper = mount(MePage)
    await flushPromises()
    wrapper.unmount()

    slow.resolve(okHistory(buildItems([{ id: "late", question: "迟到", answer: "迟到答" }])))
    await flushPromises()
    expect(errorSpy).not.toHaveBeenCalled()
    errorSpy.mockRestore()
  })
})

describe("清空历史", () => {
  async function mountWithRecord() {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([{ id: "1", question: "问题", answer: "回答" }])))
    return mountPage()
  }

  it("取消确认不发任何请求并保留记录", async () => {
    confirmMock.mockRejectedValueOnce("cancel")
    const wrapper = await mountWithRecord()

    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(clearHistoryMock).not.toHaveBeenCalled()
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(1)
    expect(successToastMock).not.toHaveBeenCalled()
  })

  it("确认后清空成功：记录清空并提示成功", async () => {
    const wrapper = await mountWithRecord()
    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()

    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(clearHistoryMock).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(0)
    expect(wrapper.find(testid("history-empty")).exists()).toBe(true)
    expect(successToastMock).toHaveBeenCalled()
  })

  it("清空失败：保留记录并给出失败反馈", async () => {
    clearHistoryMock.mockRejectedValueOnce(new HistoryRequestError("boom"))
    const wrapper = await mountWithRecord()
    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()

    expect(wrapper.findAll(testid("history-card"))).toHaveLength(1)
    expect(failToastMock).toHaveBeenCalledWith(expect.stringContaining("清空失败"))
    expect(successToastMock).not.toHaveBeenCalled()
  })

  it("清空进行中按钮禁用，重复点击只发一次请求，刷新也禁用", async () => {
    const slow = deferred()
    clearHistoryMock.mockReturnValueOnce(slow.promise)
    const wrapper = await mountWithRecord()

    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()
    expect(wrapper.find(testid("history-clear")).attributes("disabled")).toBeDefined()
    expect(wrapper.find(testid("history-refresh")).attributes("disabled")).toBeDefined()

    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()
    expect(clearHistoryMock).toHaveBeenCalledTimes(1)

    slow.resolve(undefined)
    await flushPromises()
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(0)
  })

  it("确认等待期间重复点击只弹一次确认框，取消后可再次发起", async () => {
    const slowConfirm = deferred()
    confirmMock.mockReturnValueOnce(slowConfirm.promise)
    const wrapper = await mountWithRecord()

    const button = wrapper.find(testid("history-clear"))
    const firstClick = button.trigger("click")
    const secondClick = button.trigger("click")
    await Promise.all([firstClick, secondClick])
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(clearHistoryMock).not.toHaveBeenCalled()

    slowConfirm.reject("cancel")
    await flushPromises()
    expect(clearHistoryMock).not.toHaveBeenCalled()

    // 取消后确认锁解除，可以再次发起
    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledTimes(2)
  })

  it("卸载后确认完成不会发送清空请求", async () => {
    const slowConfirm = deferred()
    confirmMock.mockReturnValueOnce(slowConfirm.promise)
    const wrapper = await mountWithRecord()

    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()
    wrapper.unmount()

    slowConfirm.resolve("confirm")
    await flushPromises()
    expect(clearHistoryMock).not.toHaveBeenCalled()
  })

  it("清空请求返回时组件已卸载：不提示、不更新", async () => {
    const slowClear = deferred()
    clearHistoryMock.mockReturnValueOnce(slowClear.promise)
    const wrapper = await mountWithRecord()

    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()
    wrapper.unmount()

    slowClear.resolve(undefined)
    await flushPromises()
    expect(successToastMock).not.toHaveBeenCalled()
    expect(failToastMock).not.toHaveBeenCalled()
  })

  it("清空进行中禁止新刷新：刷新点击不触发请求", async () => {
    const slowClear = deferred()
    clearHistoryMock.mockReturnValueOnce(slowClear.promise)
    const wrapper = await mountWithRecord()
    const callsBefore = getHistoryMock.mock.calls.length

    await wrapper.find(testid("history-clear")).trigger("click")
    await flushPromises()
    expect(wrapper.find(testid("history-refresh")).attributes("disabled")).toBeDefined()

    await wrapper.find(testid("history-refresh")).trigger("click")
    await flushPromises()
    expect(getHistoryMock.mock.calls.length).toBe(callsBefore)

    slowClear.resolve(undefined)
    await flushPromises()
    expect(wrapper.find(testid("history-empty")).exists()).toBe(true)
  })
})

describe("历史记录展示", () => {
  it("长回答默认收起，可展开、收起，aria-expanded 正确", async () => {
    const longAnswer = "答".repeat(200)
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([{ id: "long", question: "长问题", answer: longAnswer }])))
    const wrapper = await mountPage()

    const expandButton = wrapper.find(testid("history-expand"))
    expect(expandButton.attributes("aria-expanded")).toBe("false")
    expect(expandButton.text()).toBe("展开")
    expect(wrapper.find(testid("history-answer")).text().endsWith("…")).toBe(true)
    expect(wrapper.find(testid("history-answer")).text()).not.toContain(longAnswer)

    await expandButton.trigger("click")
    expect(wrapper.find(testid("history-expand")).attributes("aria-expanded")).toBe("true")
    expect(wrapper.find(testid("history-expand")).text()).toBe("收起")
    expect(wrapper.find(testid("history-answer")).text()).toContain(longAnswer)

    await wrapper.find(testid("history-expand")).trigger("click")
    expect(wrapper.find(testid("history-expand")).attributes("aria-expanded")).toBe("false")
  })

  it("回答按纯文本渲染，保留换行，不解析 HTML", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([
      { id: "1", question: "问题", answer: "<b>粗体</b>\n第二行" }
    ])))
    const wrapper = await mountPage()
    const answer = wrapper.find(testid("history-answer"))

    expect(answer.text()).toContain("<b>粗体</b>")
    expect(answer.text()).toContain("第二行")
    expect(answer.find("b").exists()).toBe(false)
  })

  it("无效时间显示时间未知，不出现 Invalid Date", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([
      { id: "1", question: "问题", answer: "回答", time: "not-a-date" }
    ])))
    const wrapper = await mountPage()

    expect(wrapper.find(testid("history-time")).text()).toBe("时间未知")
    expect(wrapper.html()).not.toContain("Invalid Date")
  })

  it("合法时间显示为格式化文本", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([
      { id: "1", question: "问题", answer: "回答", time: "2026-09-29T10:30:00" }
    ])))
    const wrapper = await mountPage()
    expect(wrapper.find(testid("history-time")).text()).toBe("2026-09-29 10:30")
  })
})

describe("显示设置", () => {
  it("两个开关具备可访问名称", async () => {
    const wrapper = await mountPage()
    expect(wrapper.find(testid("setting-show-time")).attributes("aria-label")).toBe("显示记录时间")
    expect(wrapper.find(testid("setting-expand-answers")).attributes("aria-label")).toBe("默认展开回答")
  })

  it("关闭显示时间后不渲染时间，并持久化到专属 key", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([
      { id: "1", question: "问题", answer: "回答", time: "2026-09-29T10:30:00" }
    ])))
    const wrapper = await mountPage()
    expect(wrapper.find(testid("history-time")).exists()).toBe(true)

    await wrapper.find(testid("setting-show-time")).trigger("click")
    expect(wrapper.find(testid("history-time")).exists()).toBe(false)
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY) as string).showHistoryTime).toBe(false)
  })

  it("开启默认展开回答后长回答立即展开，并持久化", async () => {
    const longAnswer = "答".repeat(200)
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([{ id: "long", question: "问题", answer: longAnswer }])))
    const wrapper = await mountPage()
    expect(wrapper.find(testid("history-expand")).attributes("aria-expanded")).toBe("false")

    await wrapper.find(testid("setting-expand-answers")).trigger("click")
    expect(wrapper.find(testid("history-expand")).attributes("aria-expanded")).toBe("true")
    expect(wrapper.find(testid("history-answer")).text()).toContain(longAnswer)
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY) as string).expandAnswers).toBe(true)
  })

  it("损坏的本地设置降级为默认值，页面仍可用", async () => {
    localStorage.setItem(SETTINGS_KEY, "{broken-json")
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([
      { id: "1", question: "问题", answer: "回答", time: "2026-09-29T10:30:00" }
    ])))
    const wrapper = await mountPage()

    expect(wrapper.find(testid("history-time")).exists()).toBe(true)
    expect(wrapper.find(testid("history-empty")).exists()).toBe(false)
    expect(wrapper.findAll(testid("history-card"))).toHaveLength(1)
  })

  it("写入失败时提示未保存，但页面设置仍然生效", async () => {
    getHistoryMock.mockResolvedValueOnce(okHistory(buildItems([
      { id: "1", question: "问题", answer: "回答", time: "2026-09-29T10:30:00" }
    ])))
    const wrapper = await mountPage()

    const spy = vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded")
    })
    try {
      await wrapper.find(testid("setting-show-time")).trigger("click")
      expect(failToastMock).toHaveBeenCalledWith(expect.stringContaining("未能保存"))
      expect(wrapper.find(testid("history-time")).exists()).toBe(false)
    } finally {
      spy.mockRestore()
    }
  })
})

describe("关于我们", () => {
  it("默认折叠，可展开查看用途、能力与免责声明，无编造联系方式", async () => {
    const wrapper = await mountPage()
    expect(wrapper.find(testid("about-detail")).exists()).toBe(false)

    const toggle = wrapper.find(testid("about-toggle"))
    expect(toggle.attributes("aria-expanded")).toBe("false")
    await toggle.trigger("click")

    const detail = wrapper.find(testid("about-detail"))
    expect(detail.exists()).toBe(true)
    expect(toggle.attributes("aria-expanded")).toBe("true")
    expect(detail.text()).toContain("校园信息查询工具")
    expect(detail.text()).toContain("咨询学校相关部门")
    expect(detail.text()).toContain("仅供参考")
    expect(detail.text()).toContain("学校最新通知")
    expect(detail.text()).not.toContain("不会编造")
    expect(detail.text()).not.toContain("历史记录功能暂未开放")
    expect(detail.text()).not.toMatch(/微信|QQ|1[3-9]\d{9}|[\w.]+@[\w.]+\.\w+/)

    await toggle.trigger("click")
    expect(wrapper.find(testid("about-detail")).exists()).toBe(false)
  })
})

describe("服务状态", () => {
  it("健康检查正常：显示在线与关键词模式，并注明仅表示服务连接正常", async () => {
    const wrapper = await mountPage()

    expect(wrapper.find(testid("service-status")).text()).toBe("在线")
    expect(wrapper.find(testid("service-mode")).text()).toBe("关键词")
    expect(wrapper.find(testid("summary-service")).text()).toBe("在线")
    expect(wrapper.find(testid("service-note")).text()).toContain("仅表示后端服务连接正常")
    expect(wrapper.text()).not.toContain("模型就绪")
    expect(wrapper.text()).not.toContain("模型可用")
  })

  it("检索模式映射：chroma 为向量，未知值为未知", async () => {
    getHealthMock.mockResolvedValueOnce({ ...HEALTHY, retrievalMode: "chroma" })
    let wrapper = await mountPage()
    expect(wrapper.find(testid("service-mode")).text()).toBe("向量")

    getHealthMock.mockResolvedValueOnce({ ...HEALTHY, retrievalMode: "hybrid" })
    wrapper = await mountPage()
    expect(wrapper.find(testid("service-mode")).text()).toBe("未知")
  })

  it("健康检查失败显示无法连接，绝不显示在线", async () => {
    getHealthMock.mockRejectedValueOnce(new Error("Network Error"))
    const wrapper = await mountPage()

    expect(wrapper.find(testid("service-status")).text()).toBe("无法连接")
    expect(wrapper.find(testid("summary-service")).text()).toBe("离线")
    expect(wrapper.find(testid("service-mode")).text()).toBe("未知")
    expect(wrapper.text()).not.toContain("在线")
  })

  it("status 非 ok 时不视为在线", async () => {
    getHealthMock.mockResolvedValueOnce({ ...HEALTHY, status: "degraded" })
    const wrapper = await mountPage()

    expect(wrapper.find(testid("service-status")).text()).toContain("服务异常")
    expect(wrapper.text()).not.toContain("在线")
  })

  it("历史接口未开放不影响健康检查结论", async () => {
    getHistoryMock.mockRejectedValueOnce(new HistoryUnavailableError())
    const wrapper = await mountPage()

    expect(wrapper.find(testid("history-unavailable")).exists()).toBe(true)
    expect(wrapper.find(testid("service-status")).text()).toBe("在线")
    expect(wrapper.find(testid("summary-service")).text()).toBe("在线")
  })

  it("重新检测会再次请求健康接口", async () => {
    const wrapper = await mountPage()
    expect(getHealthMock).toHaveBeenCalledTimes(1)

    await wrapper.find(testid("service-refresh")).trigger("click")
    await flushPromises()
    expect(getHealthMock).toHaveBeenCalledTimes(2)
  })

  it("健康检查连点：后发响应生效，先发旧响应不覆盖", async () => {
    getHealthMock.mockResolvedValue(HEALTHY)
    const wrapper = await mountPage()

    const slowFirst = deferred<HealthInfo>()
    const fastSecond = deferred<HealthInfo>()
    getHealthMock.mockReturnValueOnce(slowFirst.promise).mockReturnValueOnce(fastSecond.promise)

    const button = wrapper.find(testid("service-refresh"))
    const firstClick = button.trigger("click")
    const secondClick = button.trigger("click")
    await Promise.all([firstClick, secondClick])
    await flushPromises()

    fastSecond.resolve({ ...HEALTHY, retrievalMode: "chroma" })
    await flushPromises()
    expect(wrapper.find(testid("service-mode")).text()).toBe("向量")

    slowFirst.resolve({ ...HEALTHY, retrievalMode: "keyword" })
    await flushPromises()
    expect(wrapper.find(testid("service-mode")).text()).toBe("向量")
  })
})
