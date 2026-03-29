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
    <div class="profile-card">
      <div class="profile-title">我的</div>
      <div class="profile-desc">这里展示历史记录、设置入口和项目说明</div>
    </div>

    <div class="section-card">
      <div class="section-head">
        <span class="section-title">历史记录</span>
        <van-space>
          <van-button size="small" plain type="primary" :loading="loading" @click="fetchHistory">刷新</van-button>
          <van-button size="small" plain danger @click="handleClear">清空</van-button>
        </van-space>
      </div>

      <van-empty v-if="!loading && historyList.length === 0" description="暂无历史记录" />

      <div v-else class="history-list">
        <div v-for="item in historyList" :key="item.id" class="history-item">
          <div class="history-question">问：{{ item.question }}</div>
          <div class="history-answer">答：{{ item.answer }}</div>
          <div class="history-time">{{ item.time || "暂无时间" }}</div>
        </div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">其他入口</div>
      <van-cell title="设置" value="待接入" />
      <van-cell title="关于我们" value="校园助手项目" />
      <van-cell title="演示说明" value="大创答辩版" />
    </div>
  </div>
</template>

<style scoped>
.me-page {
  min-height: 100%;
  padding: 12px 12px 24px;
  background: #f7f8fa;
  box-sizing: border-box;
}
.profile-card,
.section-card {
  background: #fff;
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 12px;
}
.profile-title,
.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2329;
}
.profile-desc {
  margin-top: 8px;
  font-size: 13px;
  color: #646566;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.history-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.history-item {
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  padding: 12px;
}
.history-question,
.history-answer {
  font-size: 14px;
  line-height: 1.7;
  color: #323233;
}
.history-answer {
  margin-top: 6px;
}
.history-time {
  margin-top: 8px;
  font-size: 12px;
  color: #969799;
}
</style>
