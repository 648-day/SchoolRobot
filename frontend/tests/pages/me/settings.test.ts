import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  DEFAULT_PROFILE_SETTINGS,
  parseProfileSettings,
  PROFILE_SETTINGS_KEY,
  useProfileSettings
} from "@/pages/me/composables/useProfileSettings"

beforeEach(() => {
  localStorage.clear()
})

describe("parseProfileSettings 降级", () => {
  it("空值与损坏 JSON 使用默认值", () => {
    expect(parseProfileSettings(null)).toEqual({ settings: DEFAULT_PROFILE_SETTINGS, degraded: false })
    expect(parseProfileSettings("{not-json")).toEqual({ settings: DEFAULT_PROFILE_SETTINGS, degraded: true })
    expect(parseProfileSettings("[1,2]")).toEqual({ settings: DEFAULT_PROFILE_SETTINGS, degraded: true })
    expect(parseProfileSettings("\"str\"")).toEqual({ settings: DEFAULT_PROFILE_SETTINGS, degraded: true })
  })

  it("字段类型不对时该字段降级，合法字段保留", () => {
    const parsed = parseProfileSettings(JSON.stringify({ showHistoryTime: "yes", expandAnswers: true }))
    expect(parsed.degraded).toBe(true)
    expect(parsed.settings).toEqual({ showHistoryTime: true, expandAnswers: true })
  })

  it("合法值完整还原", () => {
    expect(parseProfileSettings(JSON.stringify({ showHistoryTime: false, expandAnswers: true }))).toEqual({
      settings: { showHistoryTime: false, expandAnswers: true },
      degraded: false
    })
  })
})

describe("useProfileSettings", () => {
  it("首次使用默认值：显示时间、折叠长回答", () => {
    const { settings } = useProfileSettings()
    expect(settings).toEqual(DEFAULT_PROFILE_SETTINGS)
    expect(settings.showHistoryTime).toBe(true)
    expect(settings.expandAnswers).toBe(false)
  })

  it("更新后写入专属 key，并能被新实例读回", () => {
    const first = useProfileSettings()
    expect(first.updateSetting("showHistoryTime", false)).toBe(true)
    expect(first.updateSetting("expandAnswers", true)).toBe(true)

    const stored = JSON.parse(localStorage.getItem(PROFILE_SETTINGS_KEY) as string)
    expect(stored).toEqual({ showHistoryTime: false, expandAnswers: true })

    const second = useProfileSettings()
    expect(second.settings).toEqual({ showHistoryTime: false, expandAnswers: true })
  })

  it("损坏的本地数据降级为默认值", () => {
    localStorage.setItem(PROFILE_SETTINGS_KEY, "{broken")
    const { settings, storageDegraded } = useProfileSettings()
    expect(settings).toEqual(DEFAULT_PROFILE_SETTINGS)
    expect(storageDegraded.value).toBe(true)
  })

  it("写入失败时返回 false，但内存设置仍生效", () => {
    const { settings, updateSetting } = useProfileSettings()
    const spy = vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded")
    })
    try {
      expect(updateSetting("showHistoryTime", false)).toBe(false)
      expect(settings.showHistoryTime).toBe(false)
    } finally {
      spy.mockRestore()
    }
  })

  it("存储不可用时降级且写入返回 false", () => {
    const spy = vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new Error("storage disabled")
    })
    try {
      const { settings, storageDegraded, updateSetting } = useProfileSettings()
      expect(settings).toEqual(DEFAULT_PROFILE_SETTINGS)
      expect(storageDegraded.value).toBe(true)
      expect(updateSetting("expandAnswers", true)).toBe(false)
      expect(settings.expandAnswers).toBe(true)
    } finally {
      spy.mockRestore()
    }
  })
})
