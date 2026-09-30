/** 个人中心「显示设置」：仅影响 /me 页面的展示，不代表通知 / 账号 / 主题等全局设置 */
export interface ProfileSettings {
  /** 在历史记录中显示时间 */
  showHistoryTime: boolean
  /** 默认展开较长的回答内容 */
  expandAnswers: boolean
}

export type ProfileSettingKey = keyof ProfileSettings
