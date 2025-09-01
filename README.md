# 🔍 AI 检索智能体 · LangGraph × DeepSeek × Vue

![Stack](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-flow-blue)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-black)
![Vue3](https://img.shields.io/badge/Vue-3-42b883?logo=vue.js) ![ElementPlus](https://img.shields.io/badge/Element%20Plus-2-409eff)

## ✨ 亮点
- 🧭 智能工具编排：today_date / google_search / url_summary
- 🧠 深度思考开关：需要时启用规划与多次重选
- 🛡️ 无工具兜底：到达上限或无解时，自动改用“纯文本回答”
- 🧼 上下文净化：兜底阶段屏蔽无效摘要与工具痕迹
- 🔗 链接侧栏：展示 Top 搜索结果，点击即开
- 📝 思考可见：中间过程独立泡泡，随时折叠/展开

## 🕹️ 前端交互（Vue3 + Element Plus）
- “深度思考”“网络搜索”一键切换
- 智能体思考（过程泡泡）+ 相关链接面板
- Markdown 渲染、复制、流式更新、自动滚动

> 默认头像位于 /mu.png。前端示例已内置 UI/动画与面板逻辑。

## 🧩 工作流（一句话版）
用户问题 →（可选）搜索 → 选链接 → 摘要 → 判断是否有用 → 重选/兜底 → 输出结论

- 达到重试上限 / 无可选结果 / LLM 认为不选时 → 进入“无工具兜底”，输出纯文本最终答复

## ⚡ 快速开始

后端（Agent）
1) 准备
```bash
export DEEPSEEK_API_KEY_FROM_ENV=your_api_key
pip install -r requirements.txt
```
2) 运行（CLI）
```bash
python agent/agent_graph.py
```
3) Web 场景
- 将你的 HTTP 流接口桥接到 `agent_respond_stream()` 并把每个事件原样推给前端

前端（Vue）
```bash
npm i
npm run dev
```
- 在 `@/api/chat.js` 实现 `fetchAgentReplyStream(text, options, onEntry)`，把服务端流回调给 onEntry

## 🔧 常用开关
- 深度思考：前端按钮 → 后端 `planning.enable`
- 最大重试：`planning.max_retry`（默认 3）
- 兜底标记：`planning.exhausted` 为 true 时，切换到无工具模型与兜底提示

## 📡 流式事件（超简版）
- tool_result：工具结果（如 google_search 返回 JSON 字符串）
- intermediate_step：中间想法/计划（可附最近 `query`）
- chat：最终回答（Markdown）

> 前端已按这三类事件进行渲染与面板联动。

## 🧭 使用小贴士
- 问题含“今天/现在/最新”等时间词 → 自动先取 today_date
- 需要最新信息 → 点“网络搜索”或在输入里提“请你网络搜索…”
- 兜底阶段不再调用工具，但仍给出可用的自然语言总结

—— Happy hacking!
