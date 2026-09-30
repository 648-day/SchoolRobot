import dayjs from "dayjs"

/** 回答超过该字符数时提供展开 / 收起 */
export const HISTORY_ANSWER_COLLAPSE_LIMIT = 120

export function isLongHistoryAnswer(answer: string): boolean {
  return answer.length > HISTORY_ANSWER_COLLAPSE_LIMIT
}

/** 收起状态下的回答预览：截断并加省略号 */
export function truncateHistoryAnswer(answer: string): string {
  if (!isLongHistoryAnswer(answer)) return answer
  return `${answer.slice(0, HISTORY_ANSWER_COLLAPSE_LIMIT)}…`
}

/**
 * 展示用时间格式化：无效输入返回 null，由页面显示“时间未知”，
 * 保证界面不会出现 Invalid Date。
 *
 * 字符串按契约应为 ISO 8601；对以 `YYYY-MM-DD` 开头的输入额外做日历校验，
 * 避免 dayjs 宽松解析把 13 月、2 月 30 日“滚动”成其它日期。
 */
export function formatHistoryTime(value: string | number | undefined | null): string | null {
  if (value === undefined || value === null || value === "") return null
  const day = dayjs(value)
  if (!day.isValid()) return null
  if (typeof value === "string") {
    const datePart = value.match(/^(\d{4})-(\d{2})-(\d{2})/)
    if (datePart && day.format("YYYY-MM-DD") !== `${datePart[1]}-${datePart[2]}-${datePart[3]}`) {
      return null
    }
  }
  return day.format("YYYY-MM-DD HH:mm")
}
