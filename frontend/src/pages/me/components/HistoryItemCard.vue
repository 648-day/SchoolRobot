<script setup lang="ts">
import type { HistoryDisplayItem } from "@/types/chat"
import { computed, ref, watch } from "vue"
import { formatHistoryTime, isLongHistoryAnswer, truncateHistoryAnswer } from "../utils/display"

const props = defineProps<{
  item: HistoryDisplayItem
  /** 显示记录时间（来自页面显示设置） */
  showTime: boolean
  /** 默认展开长回答（来自页面显示设置） */
  defaultExpanded: boolean
}>()

const expanded = ref(props.defaultExpanded)
// 页面开关变化时同步到卡片，保证“默认展开回答”即时生效
watch(() => props.defaultExpanded, (value) => {
  expanded.value = value
})

const isLong = computed(() => isLongHistoryAnswer(props.item.answer))
const displayAnswer = computed(() => (expanded.value ? props.item.answer : truncateHistoryAnswer(props.item.answer)))
const timeText = computed(() => formatHistoryTime(props.item.time))
</script>

<template>
  <article class="history-card" data-testid="history-card">
    <div class="history-tag">
      问答记录
    </div>
    <div class="history-question">
      问：{{ item.question }}
    </div>
    <div class="history-answer" data-testid="history-answer">
      答：{{ displayAnswer }}
    </div>
    <button
      v-if="isLong"
      type="button"
      class="history-expand"
      data-testid="history-expand"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      {{ expanded ? "收起" : "展开" }}
    </button>
    <div v-if="showTime && timeText" class="history-time" data-testid="history-time">
      {{ timeText }}
    </div>
    <div v-else-if="showTime && item.time" class="history-time" data-testid="history-time">
      时间未知
    </div>
  </article>
</template>

<style scoped>
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
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.history-expand {
  margin-top: 8px;
  padding: 4px 10px;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #f4f8ff;
  color: #2563eb;
  font-size: 12px;
  cursor: pointer;
}
.history-time {
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
}
</style>
