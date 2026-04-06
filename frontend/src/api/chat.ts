import axios from "axios"
import type { ChatResponse, HistoryResponse } from "@/types/chat"

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
  timeout: 20000
})

export async function chatWithMemory(message: string): Promise<ChatResponse> {
  try {
    const { data } = await service.post("/chat_with_memory", { message })
    return normalizeChatResponse(data)
  } catch (error) {
    const { data } = await service.post("/chat", { message })
    return normalizeChatResponse(data)
  }
}

export async function getHistory(): Promise<HistoryResponse> {
  const { data } = await service.get("/get_history")
  if (Array.isArray(data)) {
    return { items: data }
  }
  if (Array.isArray(data?.history)) {
    return { items: data.history }
  }
  if (Array.isArray(data?.items)) {
    return { items: data.items }
  }
  return { items: [] }
}

export async function clearHistory() {
  const { data } = await service.post("/clear_history")
  return data
}

function normalizeChatResponse(data: any): ChatResponse {
  if (typeof data === "string") return { answer: data }
  return {
    answer: data?.answer || data?.response || data?.message || ""
  }
}
