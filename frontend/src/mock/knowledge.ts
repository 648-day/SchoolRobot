import type { KnowledgeFeedItem } from "@/types/chat"

export const knowledgeCategories = ["新生须知", "选课指南", "保研政策", "图书馆规则", "培养方案", "课程知识点"]

export const knowledgeFeed: KnowledgeFeedItem[] = [
  {
    id: "1",
    category: "新生须知",
    title: "2025级新生报到须知",
    summary: "整理报到流程、证件材料、宿舍入住和校园卡领取等高频信息，方便新生快速完成入学准备。",
    date: "2025-09-01"
  },
  {
    id: "2",
    category: "选课指南",
    title: "本学期选课时间与操作提醒",
    summary: "包含选课开放时间、补退选阶段说明，以及选课冲突处理的基本办法。",
    date: "2025-09-05"
  },
  {
    id: "3",
    category: "图书馆规则",
    title: "图书借阅与逾期说明",
    summary: "覆盖借阅册数、借阅时长、续借规则以及逾期处理方式等图书馆常见问题。",
    date: "2025-09-07"
  },
  {
    id: "4",
    category: "保研政策",
    title: "推免资格认定常见问题",
    summary: "汇总成绩要求、竞赛加分、材料准备和时间节点等推免相关信息。",
    date: "2025-09-10"
  }
]
