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
    <div class="chat-header">
      <div class="chat-title">校园智能问答</div>
      <div class="chat-desc">基于学校资料进行问答，回答尽量贴近官方口径</div>
    </div>

    <div class="quick-questions">
      <van-button
        v-for="item in exampleQuestions"
        :key="item"
        size="small"
        round
        plain
        type="primary"
        @click="sendMessage(item)"
      >
        {{ item }}
      </van-button>
    </div>

    <div ref="listRef" class="message-list">
      <div v-for="item in messages" :key="item.id" class="message-row" :class="item.role">
        <div class="message-bubble">
          {{ item.content || (item.role === "assistant" && sending ? "正在生成回答..." : "") }}
        </div>
      </div>
    </div>

    <div class="input-panel">
      <van-field
        v-model="inputValue"
        rows="2"
        autosize
        type="textarea"
        maxlength="500"
        placeholder="请输入你的问题，例如：新生报到流程是什么？"
      />
      <van-button type="primary" block :loading="sending" :disabled="!canSend" @click="sendMessage()">
        发送
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  min-height: 100%;
  padding: 12px;
  background: #f7f8fa;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chat-header,
.quick-questions,
.message-list,
.input-panel {
  background: #fff;
  border-radius: 16px;
  padding: 14px;
}
.chat-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2329;
}
.chat-desc {
  margin-top: 8px;
  font-size: 13px;
  color: #646566;
  line-height: 1.6;
}
.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.message-list {
  flex: 1;
  min-height: 320px;
  max-height: 52vh;
  overflow-y: auto;
}
.message-row {
  display: flex;
  margin-bottom: 12px;
}
.message-row.user {
  justify-content: flex-end;
}
.message-row.assistant {
  justify-content: flex-start;
}
.message-bubble {
  max-width: 82%;
  padding: 10px 12px;
  border-radius: 14px;
  line-height: 1.7;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}
.message-row.user .message-bubble {
  background: #1989fa;
  color: #fff;
}
.message-row.assistant .message-bubble {
  background: #f2f3f5;
  color: #323233;
}
.input-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
