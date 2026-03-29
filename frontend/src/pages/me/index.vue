<script setup lang="ts">
import { onMounted, ref } from "vue"
import { showConfirmDialog, showFailToast, showSuccessToast } from "vant"
import { clearHistory, getHistory } from "@/api/chat"
import type { HistoryItem } from "@/types/chat"

const historyList = ref<HistoryItem[]>([])
const loading = ref(false)

const fetchHistory = async () => {
  loading.value = true
  try {
    const data = await getHistory()
    historyList.value = data.items || []
  } catch (error) {
    console.error(error)
    showFailToast("历史记录加载失败")
  } finally {
    loading.value = false
  }
}

const handleClear = async () => {
  try {
    await showConfirmDialog({
      title: "确认清空",
      message: "确定要清空所有历史记录吗？"
    })
    await clearHistory()
    historyList.value = []
    showSuccessToast("已清空")
  } catch {
    // cancel
  }
}

onMounted(() => {
  fetchHistory()
})
</script>

<template>
  <div class="me-page">
    <section class="profile-card">
      <div class="profile-left">
        <div class="profile-avatar">校</div>
        <div>
          <div class="profile-title">校园助手控制台</div>
          <div class="profile-desc">查看历史记录、设置说明和项目入口</div>
        </div>
      </div>
      <div class="profile-badge">DEMO</div>
    </section>

    <section class="summary-grid">
      <div class="summary-card">
        <div class="summary-value">{{ historyList.length }}</div>
        <div class="summary-label">历史会话</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">RAG</div>
        <div class="summary-label">问答模式</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">ON</div>
        <div class="summary-label">系统状态</div>
      </div>
    </section>

    <section class="panel-card">
      <div class="panel-head">
        <div>
          <div class="panel-title">历史记录</div>
          <div class="panel-subtitle">展示用户问答历史，支持清空与刷新</div>
        </div>
        <van-space>
          <van-button size="small" plain type="primary" :loading="loading" @click="fetchHistory">刷新</van-button>
          <van-button size="small" plain danger @click="handleClear">清空</van-button>
        </van-space>
      </div>

      <van-empty v-if="!loading && historyList.length === 0" description="暂无历史记录" />

      <div v-else class="history-list">
        <article v-for="item in historyList" :key="item.id" class="history-card">
          <div class="history-tag">问答记录</div>
          <div class="history-question">问：{{ item.question }}</div>
          <div class="history-answer">答：{{ item.answer }}</div>
          <div class="history-time">{{ item.time || "暂无时间" }}</div>
        </article>
      </div>
    </section>

    <section class="panel-card">
      <div class="panel-title">更多功能</div>
      <div class="entry-list">
        <div class="entry-card">
          <div>
            <div class="entry-title">设置中心</div>
            <div class="entry-desc">后续可接接口地址、主题风格、通知偏好</div>
          </div>
          <div class="entry-arrow">›</div>
        </div>
        <div class="entry-card">
          <div>
            <div class="entry-title">关于我们</div>
            <div class="entry-desc">展示项目简介、成员分工、技术栈</div>
          </div>
          <div class="entry-arrow">›</div>
        </div>
      </div>
    </section>
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
}
.profile-avatar {
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
  font-size: 18px;
  font-weight: 700;
  color: #2563eb;
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
.history-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.history-card {
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
  border: 1px solid #edf2f7;
}
.history-tag {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eef4ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}
.history-question,
.history-answer {
  margin-top: 10px;
  font-size: 14px;
  color: #334155;
  line-height: 1.8;
}
.history-time {
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
}
.entry-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.entry-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
  border: 1px solid #edf2f7;
}
.entry-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}
.entry-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}
.entry-arrow {
  font-size: 26px;
  color: #94a3b8;
}
</style>
