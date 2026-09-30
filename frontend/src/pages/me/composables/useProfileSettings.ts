import type { ProfileSettingKey, ProfileSettings } from "../types"
import { reactive, ref } from "vue"

/** 个人中心专属存储 key：只被本页面读写 */
export const PROFILE_SETTINGS_KEY = "mobvue-me-settings-key"

/** 首次进入的默认值：显示时间、折叠长回答 */
export const DEFAULT_PROFILE_SETTINGS: ProfileSettings = {
  showHistoryTime: true,
  expandAnswers: false
}

const SETTING_KEYS: ProfileSettingKey[] = ["showHistoryTime", "expandAnswers"]

function getStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage ?? null
  } catch {
    // 隐私模式等场景下访问 localStorage 本身会抛异常
    return null
  }
}

/**
 * 解析本地存储：损坏 / 类型不对的值降级为默认值，不抛异常。
 * `degraded` 表示读到了无法完整解析的内容。
 */
export function parseProfileSettings(raw: string | null): { settings: ProfileSettings, degraded: boolean } {
  const fallback = { settings: { ...DEFAULT_PROFILE_SETTINGS }, degraded: false }
  if (raw === null) return fallback
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { settings: { ...DEFAULT_PROFILE_SETTINGS }, degraded: true }
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { settings: { ...DEFAULT_PROFILE_SETTINGS }, degraded: true }
  }
  const record = parsed as Record<string, unknown>
  const settings = { ...DEFAULT_PROFILE_SETTINGS }
  let degraded = false
  for (const key of SETTING_KEYS) {
    if (key in record) {
      if (typeof record[key] === "boolean") settings[key] = record[key] as boolean
      else degraded = true
    }
  }
  return { settings, degraded }
}

/**
 * 个人中心显示设置（localStorage 持久化）。
 *
 * - 读取异常 / 存储禁用：降级为默认值，页面照常可用（`storageDegraded` 为 true）。
 * - 写入失败：`updateSetting` 返回 false，调用方提示“未保存”，但内存中的设置仍然生效。
 */
export function useProfileSettings() {
  const settings = reactive<ProfileSettings>({ ...DEFAULT_PROFILE_SETTINGS })
  const storageDegraded = ref(false)
  const storage = getStorage()

  if (storage) {
    try {
      const { settings: loaded, degraded } = parseProfileSettings(storage.getItem(PROFILE_SETTINGS_KEY))
      Object.assign(settings, loaded)
      storageDegraded.value = degraded
    } catch {
      storageDegraded.value = true
    }
  } else {
    storageDegraded.value = true
  }

  function updateSetting(key: ProfileSettingKey, value: boolean): boolean {
    settings[key] = value
    if (!storage) return false
    try {
      storage.setItem(PROFILE_SETTINGS_KEY, JSON.stringify({ ...settings }))
      return true
    } catch {
      return false
    }
  }

  return { settings, storageDegraded, updateSetting }
}
