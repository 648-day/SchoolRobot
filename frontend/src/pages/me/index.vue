<script setup lang="ts">
import type { ProfileSettingKey } from "./types"
import type { HistoryErrorKind } from "@/api/chat"
import type { HealthInfo, HistoryDisplayItem } from "@/types/chat"
import { useTitle } from "@@/composables/useTitle"
import {
  showConfirmDialog,
  showFailToast,
  showSuccessToast,
  Button as VanButton,
  Empty as VanEmpty,
  Loading as VanLoading,
  Space as VanSpace
} from "vant"
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { clearHistory, getHealth, getHistory, historyErrorKindOf } from "@/api/chat"
import AboutPanel from "./components/AboutPanel.vue"
import HistoryItemCard from "./components/HistoryItemCard.vue"
import ServiceStatusPanel from "./components/ServiceStatusPanel.vue"
import SettingsPanel from "./components/SettingsPanel.vue"
import { useProfileSettings } from "./composables/useProfileSettings"
// 显式导入所用 Vant 组件样式（显式组件导入不会被 unplugin 自动注入样式）
import "vant/es/button/style/index"
import "vant/es/dialog/style/index"
import "vant/es/empty/style/index"
import "vant/es/loading/style/index"
import "vant/es/space/style/index"
import "vant/es/toast/style/index"

type HistoryStatus = "loading" | "success" | "unavailable" | "error" | "format"
type HealthStatus = "loading" | "ok" | "error"

const RETRIEVAL_MODE_TEXT: Record<string, string> = {
  keyword: "关键词",
  chroma: "向量"
}

/** 历史加载失败时的用户提示，按错误分类展示，不把失败当空历史 */
const HISTORY_ERROR_TEXT: Record<HistoryErrorKind, string> = {
  unavailable: "历史记录暂未开放，当前问答暂不保存历史。",
  request: "历史记录加载失败，请检查网络或后端服务后重试。",
  format: "历史数据格式异常，暂时无法展示。"
}

const { setTitle } = useTitle()
const { settings, updateSetting } = useProfileSettings()

const historyItems = ref<HistoryDisplayItem[]>([])
const historyStatus = ref<HistoryStatus>("loading")
/** 刷新失败但保留了上一次的记录 */
const historyStale = ref(false)
const staleErrorKind = ref<HistoryErrorKind | null>(null)
/** 清空确认框等待中（独立确认锁，确认期间禁止重复点击与新刷新） */
const confirming = ref(false)
/** 清空请求进行中 */
const clearing = ref(false)
/** 历史请求进行中（首次加载或刷新） */
const refreshing = ref(false)

const healthStatus = ref<HealthStatus>("loading")
const healthInfo = ref<HealthInfo | null>(null)

// 请求序号与卸载标记：旧响应（含清空后返回的刷新响应）与被卸载组件的响应不得更新状态
let fetchSeq = 0
let healthSeq = 0
let disposed = false

const isLoading = computed(() => historyStatus.value === "loading")
const canClear = computed(() =>
  !refreshing.value
  && !clearing.value
  && !confirming.value
  && historyStatus.value === "success"
  && !historyStale.value
  && historyItems.value.length > 0
)
const historyNoticeKind = computed<HistoryErrorKind | null>(() => {
  if (historyStatus.value === "unavailable") return "unavailable"
  if (historyStatus.value === "format") return "format"
  if (historyStatus.value === "error") return "request"
  return null
})
const historyNoticeText = computed(() => (historyNoticeKind.value ? HISTORY_ERROR_TEXT[historyNoticeKind.value] : ""))
const staleNoticeText = computed(() => (staleErrorKind.value ? `刷新失败：${HISTORY_ERROR_TEXT[staleErrorKind.value]} 以下为上次成功加载的记录，可能不是最新。` : ""))
const historyCountText = computed(() => (historyStatus.value === "success" ? String(historyItems.value.length) : "—"))
const retrievalModeText = computed(() => {
  if (healthStatus.value !== "ok" || !healthInfo.value) return "未知"
  return RETRIEVAL_MODE_TEXT[healthInfo.value.retrievalMode] ?? "未知"
})
const serviceText = computed(() => {
  if (healthStatus.value === "loading") return "检测中"
  return healthStatus.value === "ok" ? "在线" : "离线"
})

async function fetchHistory() {
  // 清空确认 / 清空进行中不接受新刷新
  if (clearing.value || confirming.value) return
  const seq = ++fetchSeq
  refreshing.value = true
  if (historyItems.value.length === 0) {
    historyStatus.value = "loading"
    historyStale.value = false
    staleErrorKind.value = null
  }
  try {
    const data = await getHistory()
    if (disposed || seq !== fetchSeq) return
    historyItems.value = data.items
    historyStatus.value = "success"
    historyStale.value = false
    staleErrorKind.value = null
  } catch (error) {
    if (disposed || seq !== fetchSeq) return
    const kind = historyErrorKindOf(error)
    if (historyItems.value.length > 0) {
      // 保留旧记录，但明确标注不是最新
      historyStale.value = true
      staleErrorKind.value = kind
    } else {
      historyStatus.value = kind === "unavailable" ? "unavailable" : kind === "format" ? "format" : "error"
      historyStale.value = false
      staleErrorKind.value = null
    }
  } finally {
    // 只有最新一次请求才能结束“刷新中”状态
    if (!disposed && seq === fetchSeq) refreshing.value = false
  }
}

async function fetchHealth() {
  const seq = ++healthSeq
  healthStatus.value = "loading"
  try {
    const info = await getHealth()
    if (disposed || seq !== healthSeq) return
    healthInfo.value = info
    healthStatus.value = info.status === "ok" ? "ok" : "error"
  } catch {
    if (disposed || seq !== healthSeq) return
    healthInfo.value = null
    healthStatus.value = "error"
  }
}

async function handleClear() {
  if (!canClear.value) return
  // 确认等待期间先上锁：重复点击不再弹窗
  confirming.value = true
  let confirmed = false
  try {
    await showConfirmDialog({
      title: "确认清空",
      message: "确定要清空全部历史记录吗？清空后无法恢复。"
    })
    confirmed = true
  } catch {
    // 用户取消：不发任何请求
    confirmed = false
  } finally {
    if (!disposed) confirming.value = false
  }
  // 取消、或确认期间已离开页面：不发清空请求
  if (!confirmed || disposed) return

  clearing.value = true
  fetchSeq += 1 // 防御：理论上存在的在途刷新失效，旧响应不能把记录“复活”
  try {
    await clearHistory()
    if (disposed) return
    historyItems.value = []
    historyStatus.value = "success"
    historyStale.value = false
    staleErrorKind.value = null
    showSuccessToast("已清空历史记录")
  } catch (error) {
    // 清空失败：保留现有记录，明确提示
    if (disposed) return
    showFailToast(historyErrorKindOf(error) === "unavailable" ? "清空失败：历史记录暂未开放" : "清空失败，请稍后重试")
  } finally {
    if (!disposed) clearing.value = false
  }
}

function handleSettingUpdate(key: ProfileSettingKey, value: boolean) {
  const saved = updateSetting(key, value)
  if (!saved) showFailToast("设置已修改，但未能保存到本地")
}

onMounted(() => {
  setTitle("个人中心")
  fetchHistory()
  fetchHealth()
})

onBeforeUnmount(() => {
  disposed = true
  fetchSeq += 1
  healthSeq += 1
})
</script>

<template>
  <div class="me-page">
    <section class="profile-card">
      <div class="profile-left">
        <div class="profile-avatar">
          校
        </div>
        <div>
          <div class="profile-title">
            个人中心
          </div>
          <div class="profile-desc">
            历史记录、显示设置与项目说明
          </div>
        </div>
      </div>
      <div class="profile-badge">
        校园助手
      </div>
    </section>

    <section class="summary-grid">
      <div class="summary-card">
        <div class="summary-value" data-testid="summary-history">
          {{ historyCountText }}
        </div>
        <div class="summary-label">
          历史记录
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-value" data-testid="summary-mode">
          {{ retrievalModeText }}
        </div>
        <div class="summary-label">
          检索模式
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-value" data-testid="summary-service">
          {{ serviceText }}
        </div>
        <div class="summary-label">
          服务状态
        </div>
      </div>
    </section>

    <ServiceStatusPanel :status="healthStatus" :info="healthInfo" @refresh="fetchHealth" />

    <section class="panel-card" data-testid="history-panel">
      <div class="panel-head">
        <div class="panel-head-text">
          <div class="panel-title">
            历史记录
          </div>
          <div class="panel-subtitle">
            查看问答记录，支持刷新与清空
          </div>
        </div>
        <VanSpace>
          <VanButton
            size="small"
            plain
            type="primary"
            data-testid="history-refresh"
            :loading="refreshing"
            :disabled="refreshing || clearing || confirming"
            @click="fetchHistory"
          >
            刷新
          </VanButton>
          <VanButton
            size="small"
            plain
            type="danger"
            data-testid="history-clear"
            :loading="clearing"
            :disabled="!canClear"
            @click="handleClear"
          >
            清空
          </VanButton>
        </VanSpace>
      </div>

      <div v-if="refreshing && historyItems.length > 0" class="history-notice is-refreshing" data-testid="history-refreshing">
        <div class="notice-text">
          正在刷新历史记录…
        </div>
      </div>

      <div v-if="historyStale && !refreshing" class="history-notice is-stale" data-testid="history-stale">
        {{ staleNoticeText }}
      </div>

      <div v-if="isLoading" class="history-loading" data-testid="history-loading">
        <VanLoading size="20">
          正在加载历史记录…
        </VanLoading>
      </div>

      <div v-else-if="historyStatus === 'unavailable'" class="history-notice" data-testid="history-unavailable">
        <div class="notice-text">
          {{ HISTORY_ERROR_TEXT.unavailable }}
        </div>
        <VanButton size="small" plain type="primary" data-testid="history-retry" @click="fetchHistory">
          重试
        </VanButton>
      </div>

      <div v-else-if="historyStatus === 'error' || historyStatus === 'format'" class="history-notice" data-testid="history-error">
        <div class="notice-text">
          {{ historyNoticeText }}
        </div>
        <VanButton size="small" plain type="primary" data-testid="history-retry" @click="fetchHistory">
          重试
        </VanButton>
      </div>

      <VanEmpty v-else-if="historyItems.length === 0" description="暂无历史记录" data-testid="history-empty" />

      <div v-else class="history-list" data-testid="history-list">
        <HistoryItemCard
          v-for="item in historyItems"
          :key="item.key"
          :item="item"
          :show-time="settings.showHistoryTime"
          :default-expanded="settings.expandAnswers"
        />
      </div>
    </section>

    <SettingsPanel :settings="settings" @update="handleSettingUpdate" />

    <AboutPanel />
  </div>
</template>

<style scoped>
.me-page {
  min-height: 100%;
  padding: 14px 14px 24px;
  background:
    radial-gradient(circle at top right, rgba(64, 158, 255, 0.14), transparent 22%),
    linear-gradient(180deg, #eef5ff 0%, #f7f8fa 36%, #f7f8fa 100%);
  box-sizing: border-box;
}
.profile-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px;
  border-radius: 24px;
  color: #fff;
  background: linear-gradient(135deg, #0f5ae0 0%, #4f8dff 52%, #8ab8ff 100%);
  box-shadow: 0 16px 34px rgba(15, 90, 224, 0.22);
}
.profile-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.profile-avatar {
  flex: none;
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-size: 22px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.16);
}
.profile-title {
  font-size: 19px;
  font-weight: 700;
}
.profile-desc {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.84);
}
.profile-badge {
  flex: none;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.16);
}
.summary-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.summary-card {
  padding: 14px 10px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  text-align: center;
}
.summary-value {
  font-size: 17px;
  font-weight: 700;
  color: #2563eb;
  overflow-wrap: anywhere;
}
.summary-label {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.panel-card {
  margin-top: 14px;
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.panel-head-text {
  min-width: 0;
}
.panel-title {
  font-size: 17px;
  font-weight: 700;
  color: #1f2937;
}
.panel-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}
.history-notice {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: #fff7f5;
  border: 1px solid #fde4dc;
}
.history-notice.is-stale {
  background: #fffbeb;
  border-color: #fde68a;
}
.history-notice.is-refreshing {
  background: #f0f7ff;
  border-color: #dbeafe;
}
.notice-text {
  font-size: 13px;
  line-height: 1.8;
  color: #475569;
}
.history-loading {
  margin-top: 18px;
  display: flex;
  justify-content: center;
}
.history-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
