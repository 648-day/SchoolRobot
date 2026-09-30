# 个人中心（/me）阶段测试报告

> 更新：2026-09-30 · 分支：`xiangliang` · 范围：C 负责的 `/me` 个人中心（历史展示与清空状态、
> 显示设置、关于我们、服务状态）。
>
> 相关文档：[progress.md](./progress.md)（进度入口）、[student_c_plan.md](./student_c_plan.md)
> （阶段计划与边界）、[api.md](./api.md)（历史 / 健康接口契约）。
>
> **结论**：个人中心前端自测（vitest / vue-tsc / build / lint）全部通过，Codex 独立浏览器
> 验收通过（2026-09-30）。**真实历史后端（A 负责）仍未实现**：`GET /get_history` 当前 404，
> 页面按“未开放”展示；本报告不宣称真实历史持久化或真实清空已联调通过。

## 1. 自测命令与结果（2026-09-30，本机）

```powershell
cd frontend
pnpm exec vitest run                     # 6 files, 81 passed
pnpm exec vue-tsc --noEmit               # 退出 0
pnpm build                               # vue-tsc + vite build 成功；PWA precache 81 entries
pnpm exec eslint <本轮新增/修改的文件>   # 退出 0（只针对本轮文件，未运行全仓 --fix）
```

- 测试文件与用例数：`tests/api/chat.test.ts` 21、`tests/pages/me/page.test.ts` 36、
  `tests/pages/me/settings.test.ts` 8、`tests/pages/me/display.test.ts` 5，
  加原有 `tests/demo.test.ts` 2、`tests/utils/validate.test.ts` 9，共 **81 passed**。
- 生产构建后核验：`dist` CSS 中包含 `.van-button / .van-switch / .van-dialog / .van-toast /
  .van-space / .van-empty / .van-loading` 等样式 —— 显式导入 Vant 组件时同步显式导入其样式，
  避免浏览器里组件无样式（首轮浏览器验收发现的问题，已修复并复验）。
- 生成声明：`frontend/types/auto/components.d.ts` 恢复为本轮开始时的用户版本
  （含 VanCellGroup / VanForm 等），`git hash-object` = `2b124f3924ca4659c8567b206d294f6f5c9a786e`；
  `auto-imports.d.ts` 保持基线 `6abdace96058f5fdf7a836649e18727102a4f052`。

## 2. 自测覆盖范围（要点）

### 2.1 API 适配（`tests/api/chat.test.ts`，全部 mock axios，离线）

- 历史结构：兼容 `[]`、`{items: []}`、`{history: []}`（同时存在时 history 优先，与旧实现一致）；
  其它结构抛 `HistoryFormatError`，不静默当空。
- 条目校验：`question` / `answer` 必须为字符串；`id`、`time` 允许字符串或数字；
  非法条目整体拒绝。
- 展示 key：`JSON.stringify([id, index])`，覆盖重复 id、缺失 id、`#` 后缀 id、生成 id 撞名等
  场景，key 在同一响应内唯一；文档说明顺序变化时 key 会变化，后端契约仍要求唯一 id。
- 错误分类：404 / 501 → 未开放；其它网络 / 服务错误 → 请求失败；格式错误单独分类。
- 清空成功契约：2xx 且响应体没有显式失败标记才算成功；`{success:false}`、`{ok:false}`、
  `{status:"error"|"failed"|"fail"}` 一律拒绝（服务拒绝删除时不清空界面）。
- `/health`：字段解析、缺 `status` 视为失败、网络错误抛 `HealthCheckError`。
- `chatWithMemory` 回落行为回归：首次请求任意失败都会回落到 `/chat`，字符串 / `response`
  字段归一化不变。

### 2.2 页面行为（`tests/pages/me/*`，mock `@/api/chat` 与 Vant dialog/toast，happy-dom）

- 状态区分：加载中、成功空、成功有记录、404/501 未开放（固定文案 + 重试）、
  网络 / 服务错误、响应格式异常；失败与未开放都不会显示成空历史。
- 刷新失败保留旧记录并标注“可能不是最新”，无“已同步”假状态；此时清空禁用。
- 清空：必须先确认；取消零请求；成功才清空并提示；失败保留记录并提示；
  确认等待期间有独立确认锁（同一帧连点只弹一次确认框，取消后可再次发起）；
  清空 / 确认期间刷新禁用且点击不触发请求；清空中清空按钮禁用。
- 竞态与卸载：同一帧连点刷新时以最新请求为准，旧响应不覆盖；组件卸载后确认完成不发清空
  请求；清空响应在卸载后返回时不提示、不更新。
- 设置：两个开关有可访问名称（aria-label）；“显示记录时间”“默认展开回答”持久化到专属 key
  `mobvue-me-settings-key`；损坏 / 类型不对的本地值降级为默认值；写失败提示未保存但页面
  仍生效；存储不可用降级。
- 展示：长回答默认折叠、展开 / 收起按钮带 `aria-expanded` 且为原生 button；
  回答纯文本渲染、保留换行、不解析 HTML；无效时间显示“时间未知”，不出现 Invalid Date。
- 关于我们：默认折叠、可展开 / 收起，内容为项目用途、现阶段能力（资料缺失时提示咨询学校
  相关部门）、仅供参考与“以学校最新通知为准”；无编造姓名 / 联系方式。
- 服务状态：真实 `/health` 语义映射（keyword → 关键词、chroma → 向量、其它 → 未知）；
  失败或 `status !== "ok"` 不显示在线；历史接口失败不影响健康结论；连点重新检测时
  以最新响应为准。

## 3. Codex 独立验收

### 3.1 真实环境浏览器验收（2026-09-30，Edge headless；真实 Vite :3333 + FastAPI :8000）

通过项（真实接口 / 真实页面）：

- 真实演示登录进入 `/me`；
- 真实 `GET /get_history` 返回 404 → 页面显示“历史记录暂未开放，当前问答暂不保存历史。”
  且清空按钮禁用；
- 真实 `GET /health` → 检索模式“关键词”、服务状态“在线”，页面注明“仅表示后端服务连接
  正常，不代表问答与检索的依赖均可用”；
- 设置中关闭“显示记录时间”后重载页面仍保留（localStorage 持久化生效）；
- “关于我们”展开后出现“以学校最新通知和老师答复为准”说明；
- 320px / 375px 宽度下 `document.scrollWidth === viewport`，无横向溢出；
- switch 样式正常，刷新 / 清空按钮恢复横排（样式导入修复生效）；
- 页面 `pageerror` 为空。

### 3.2 浏览器内隔离拦截（mock 响应，仅验证 UI 分支，不是真实历史后端）

- `/health` 503 → 页面显示“无法连接 / 离线”；
- 历史有记录 → 长回答可展开；
- 清空取消 → 零 POST 请求；`{success:false}` → 保留记录并 toast 失败；
  `{success:true}` → 显示空历史；
- 真实 Vant dialog（历史响应为 mock，组件与样式为真实）`position: fixed`。

> 说明：3.2 的拦截响应只用于验证前端分支，**不代表历史接口已实现、历史数据会持久化或
> 真实清空已验证**。截图保存在系统 TEMP，不纳入仓库。

## 4. 已知限制与风险

1. **真实历史后端未实现（A 负责）**：`/get_history`、`/clear_history` 当前 404；页面按
   “未开放”展示；真实历史持久化、真实清空、分页等尚未联调。
2. `/health` 只报告进程与配置（`external_dependencies_checked=false`），不代表大模型 /
   向量库可用；页面已按此文案展示，`rag_service_ready` 未被当作模型就绪。
3. 个人中心不依赖 Chroma / BGE；真实 Chroma + BGE 全链路属于后端后续阶段。
4. 本阶段的浏览器验收由 Codex 完成；本报告只记录其结论，不额外宣称其它浏览器 / 设备覆盖。

## 5. 结论

- 个人中心前端范围（历史展示状态机、清空确认与竞态、显示设置、关于我们、服务状态）
  代码与测试完成，81 项前端测试、类型检查、生产构建与目标文件 lint 全部通过；
- 真实浏览器验收通过（Codex，2026-09-30），mock 与真实接口的边界已在上文区分；
- 剩余联调依赖 A 的历史接口，见 [progress.md](./progress.md) 的“下一步”。
