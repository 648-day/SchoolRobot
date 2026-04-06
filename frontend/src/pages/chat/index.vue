<script setup lang="ts">
import { computed, nextTick, ref } from "vue"
import { showFailToast } from "vant"
import { chatWithMemory } from "@/api/chat"
import type { ChatMessage } from "@/types/chat"

const inputValue = ref("")
const sending = ref(false)
const messages = ref<ChatMessage[]>([
  {
    id: "welcome",
    role: "assistant",
    content: "你好，我是校园智能助手。你可以问我新生须知、选课、培养方案、图书馆规则等问题。"
  }
])

const exampleQuestions = [
  "新生报到要准备什么材料？",
  "选课冲突怎么处理？",
  "图书馆借阅规则是什么？"
]

const listRef = ref<HTMLElement | null>(null)

const canSend = computed(() => !!inputValue.value.trim() && !sending.value)

const scrollToBottom = async () => {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

const pushUserMessage = (text: string) => {
  messages.value.push({
    id: `user-${Date.now()}`,
    role: "user",
    content: text
  })
}

const pushAssistantPlaceholder = () => {
  const msg: ChatMessage = {
    id: `assistant-${Date.now()}`,
    role: "assistant",
    content: ""
  }
  messages.value.push(msg)
  return msg
}

const fillByNormalResponse = async (question: string) => {
  const reply = pushAssistantPlaceholder()
  await scrollToBottom()
  const data = await chatWithMemory(question)
  reply.content = data.answer || "抱歉，我暂时没有检索到合适内容。"
  await scrollToBottom()
}

const sendMessage = async (preset?: string) => {
  const text = (preset ?? inputValue.value).trim()
  if (!text || sending.value) return

  inputValue.value = ""
  pushUserMessage(text)
  sending.value = true
  await scrollToBottom()

  try {
    await fillByNormalResponse(text)
  } catch (error) {
    console.error(error)
    showFailToast("请求失败，请检查后端接口")
    messages.value.push({
      id: `error-${Date.now()}`,
      role: "assistant",
      content: "请求失败，请确认后端 /chat_with_memory 或备用接口是否已启动。"
    })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}
</script>

<template>
  <div class="chat-page">
    <section class="chat-hero">
      <div class="chat-hero-title">智能问答</div>
      <div class="chat-hero-desc">基于学校资料检索回答，适合做校园政策、选课、图书馆等场景演示。</div>
    </section>

    <section class="quick-panel">
      <div class="quick-title">快捷问题</div>
      <div class="quick-list">
        <div v-for="item in exampleQuestions" :key="item" class="quick-chip" @click="sendMessage(item)">
          {{ item }}
        </div>
      </div>
    </section>

    <section ref="listRef" class="message-panel">
      <div v-for="item in messages" :key="item.id" class="message-row" :class="item.role">
        <div v-if="item.role === 'assistant'" class="avatar ai">AI</div>
        <div class="message-bubble" :class="item.role">
          {{ item.content || (item.role === "assistant" && sending ? "正在生成回答..." : "") }}
        </div>
        <div v-if="item.role === 'user'" class="avatar user">我</div>
      </div>
    </section>

    <section class="composer">
      <div class="composer-box">
        <van-field
          v-model="inputValue"
          rows="2"
          autosize
          type="textarea"
          maxlength="500"
          placeholder="请输入你的问题，例如：新生报到流程是什么？"
        />
      </div>
      <van-button class="send-btn" type="primary" block :loading="sending" :disabled="!canSend" @click="sendMessage()">
        发送问题
      </van-button>
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  min-height: 100%;
  padding: 14px 14px 22px;
  background:
    radial-gradient(circle at top left, rgba(42, 126, 255, 0.14), transparent 22%),
    linear-gradient(180deg, #eff5ff 0%, #f8fafc 36%, #f7f8fa 100%);
  box-sizing: border-box;
}
.chat-hero {
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(135deg, #0f5ae0 0%, #4f8dff 52%, #8ab8ff 100%);
  color: #fff;
  box-shadow: 0 16px 34px rgba(15, 90, 224, 0.22);
}
.chat-hero-title {
  font-size: 24px;
  font-weight: 700;
}
.chat-hero-desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.75;
  color: rgba(255, 255, 255, 0.88);
}
.quick-panel,
.message-panel,
.composer {
  margin-top: 14px;
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(12px);
}
.quick-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 12px;
}
.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.quick-chip {
  padding: 10px 14px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f4f8ff 0%, #eef4ff 100%);
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid #dbeafe;
}
.message-panel {
  min-height: 360px;
  max-height: 52vh;
  overflow-y: auto;
}
.message-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 14px;
}
.message-row.user {
  justify-content: flex-end;
}
.message-row.assistant {
  justify-content: flex-start;
}
.avatar {
  flex: none;
  width: 32px;
  height: 32px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
}
.avatar.ai {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #1d4ed8;
}
.avatar.user {
  background: linear-gradient(135deg, #2563eb 0%, #5b9aff 100%);
  color: #fff;
}
.message-bubble {
  max-width: 76%;
  padding: 12px 14px;
  border-radius: 18px;
  line-height: 1.8;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}
.message-bubble.user {
  background: linear-gradient(135deg, #2563eb 0%, #5b9aff 100%);
  color: #fff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.2);
}
.message-bubble.assistant {
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  color: #334155;
  border: 1px solid #e8eef6;
  border-bottom-left-radius: 6px;
}
.composer-box {
  padding: 6px;
  border-radius: 18px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}
.send-btn {
  margin-top: 12px;
  height: 44px;
  border-radius: 14px;
}
</style>
