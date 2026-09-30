import { describe, expect, it } from "vitest"
import { formatHistoryTime, HISTORY_ANSWER_COLLAPSE_LIMIT, isLongHistoryAnswer, truncateHistoryAnswer } from "@/pages/me/utils/display"

describe("长回答折叠工具", () => {
  it("按阈值判断是否长回答", () => {
    expect(isLongHistoryAnswer("短".repeat(HISTORY_ANSWER_COLLAPSE_LIMIT))).toBe(false)
    expect(isLongHistoryAnswer("长".repeat(HISTORY_ANSWER_COLLAPSE_LIMIT + 1))).toBe(true)
  })

  it("截断后保留前缀并加省略号", () => {
    const answer = "答".repeat(HISTORY_ANSWER_COLLAPSE_LIMIT + 10)
    const truncated = truncateHistoryAnswer(answer)
    expect(truncated.endsWith("…")).toBe(true)
    expect(truncated.length).toBe(HISTORY_ANSWER_COLLAPSE_LIMIT + 1)
    expect(answer.startsWith(truncated.slice(0, -1))).toBe(true)
  })

  it("短回答原样返回", () => {
    expect(truncateHistoryAnswer("短回答")).toBe("短回答")
  })
})

describe("时间格式化", () => {
  it("合法时间格式化为 YYYY-MM-DD HH:mm", () => {
    expect(formatHistoryTime("2026-09-29T10:30:00")).toBe("2026-09-29 10:30")
  })

  it("无效或缺失时间返回 null，不产生 Invalid Date", () => {
    expect(formatHistoryTime("not-a-date")).toBeNull()
    expect(formatHistoryTime("2026-13-40T99:00:00")).toBeNull()
    expect(formatHistoryTime(undefined)).toBeNull()
    expect(formatHistoryTime("")).toBeNull()
    expect(formatHistoryTime(Number.NaN)).toBeNull()
  })
})
