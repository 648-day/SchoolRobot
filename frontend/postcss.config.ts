// 修改配置后重启服务生效
export default {
  plugins: {
    // 自动添加浏览器前缀
    "autoprefixer": {},
    // 移动端适配插件
    "postcss-mobile-forever": {
      // UI 设计稿宽度
      viewportWidth: (file: string) => file.includes("vant") ? 375 : 375,
      // 限制视图的最大宽度
      maxDisplayWidth: 750,
      // 页面最外层选择器
      appSelector: "#app",
      // 是否对「页面最外层选择器」对应的元素进行描边
      border: true,
      // 转换单位后保留的小数点位数
      unitPrecision: 3,
      // 转换后的单位
      mobileUnit: "vw",
      // 需要转换的属性
      propList: ["*"],
      // 忽略的选择器
      selectorBlackList: [".ignore", ".keep-px"],
      // 忽略的属性
      propertyBlackList: {
        ".van-icon": "font"
      },
      // 忽略的属性值
      valueBlackList: ["1px"],
      // 忽略的目录或文件
      exclude: [],
      // 包含块是根元素的选择器列表
      rootContainingBlockSelectorList: [".van-tabbar", ".van-popup"]
    }
  }
}
