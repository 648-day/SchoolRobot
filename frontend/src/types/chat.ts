export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
}

export interface ChatResponse {
  answer: string
}

export interface HistoryItem {
  id: string
  question: string
  answer: string
  time?: string
}

export interface HistoryResponse {
  items: HistoryItem[]
}

export interface KnowledgeFeedItem {
  id: string
  category: string
  title: string
  summary: string
  date: string
}
