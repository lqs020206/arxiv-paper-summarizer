# ArXiv 论文摘要生成器 (Semantic Scholar + Moonshot AI)





## 1. 项目概述



本项目是一个**无服务器（Serverless）架构**的学术论文调研工具。它允许用户通过关键词搜索特定时间范围内的论文，并利用大语言模型（Moonshot AI / Kimi）自动生成中文摘要。



### 核心特性



- **深度搜索**：解决了 Semantic Scholar API 默认按引用量排序导致“搜不到最新论文”的问题，通过并发/串行抓取前 100-1000 篇论文进行本地过滤。
- **精确筛选**：支持精确到“天”的日期筛选。
- **防封锁机制**：内置智能重试（Retry）和冷却（Cooldown）逻辑，防止触发 API 的 429（请求过多）限制。
- **隐私安全**：API Key 存储在后端 Worker 中，前端源码不暴露任何敏感信息。

------



## 2. 系统架构



项目由两部分组成，均托管在 Cloudflare 平台上：

1. **前端 (Frontend)**: `index.html` (托管于 Cloudflare Pages)
   - 负责用户界面、逻辑控制、数据清洗和展示。
2. **后端/中继 (Backend)**: `worker.js` (托管于 Cloudflare Workers)
   - 负责请求转发、解决跨域 (CORS) 问题、隐藏 API Key。

Code snippet

```
graph LR
    User[用户浏览器] -- 1. 发起搜索/摘要请求 --> Worker[Cloudflare Worker]
    Worker -- 2. 转发搜索请求 --> SS[Semantic Scholar API]
    Worker -- 3. 转发摘要请求 (带Key) --> Moon[Moonshot AI API]
    SS -- 返回论文数据 --> Worker
    Moon -- 返回摘要结果 --> Worker
    Worker -- 4. 返回最终数据 --> User
```

------



## 3. 后端详解 (`worker.js`)



Worker 是系统的“中转站”和“保镖”。



### 主要函数：`fetch(request, env, ctx)`



这是 Cloudflare Worker 的入口函数，监听所有发往该 Worker 的 HTTP 请求。



#### 核心逻辑：



1. **CORS 处理 (Cross-Origin Resource Sharing)**
   - **代码**：`const corsHeaders = { ... }`
   - **作用**：允许您的前端网页（Pages）跨域访问这个后端接口。如果没有这一步，浏览器会拦截请求。
   - **预检请求**：处理 `OPTIONS` 请求，告诉浏览器“允许访问”。
2. **路由分发** 根据 URL 的路径（pathname）将请求分发给不同的上游服务：
   - **路由 `/arxiv` (论文搜索)**
     - **作用**：代理访问 Semantic Scholar API。
     - **逻辑**：接收前端传来的 `search_query` (查询词) 和 `offset` (翻页偏移量)。
     - **关键参数**：`limit=100` (每次取100篇), `fields=...,publicationDate` (强制要求返回日期字段)。
     - **返回值**：将 Semantic Scholar 返回的 JSON 数据原样转发给前端。
   - **路由 `/moonshot` (AI 摘要)**
     - **作用**：代理访问 Moonshot AI 接口。
     - **安全机制**：**这是最重要的一点**。它从环境变量 `env.MOONSHOT_API_KEY` 中读取密钥，并将其添加到请求头 (`Authorization: Bearer ...`) 中。
     - **意义**：前端发送请求时不需要带 Key，防止恶意用户通过“查看网页源代码”窃取您的额度。

------



## 4. 前端详解 (`index.html`)



前端不仅是界面，还承担了复杂的**业务逻辑**（如深度搜索、去重、重试）。



### 关键函数解析





#### 1. `searchArxiv(keyword, startDate, endDate)`



这是整个项目的核心搜索引擎。

- **作用**：根据用户输入，从数据库中挖掘符合条件的论文。
- **逻辑流程**：
  1. **年份锁定**：计算用户选择的年份范围（如 `2024-2025`），将查询词修改为 `keyword year:2024-2025`。这能让 API 先在服务器端剔除老旧的高引论文。
  2. **循环翻页 (Pagination Loop)**：根据用户选择的深度（如 300 篇），循环发起请求（Offset 0, 100, 200...）。
  3. **防封锁与重试**：
     - 如果遇到 `429` 错误，代码会**暂停 10 秒** (`await sleep(10000)`) 然后重试。
     - 每成功抓取一页，**强制等待 4 秒**，模拟人类行为，避免 API 速率限制。
  4. **本地精确筛选**：
     - API 只能按年筛选，无法按天筛选。
     - 此函数拿到数据后，会逐个比对 `publicationDate` 是否在 `startDate` 和 `endDate` 之间。不在范围内的直接丢弃。
  5. **去重**：防止 API 在翻页过程中因数据更新导致的数据重复。



#### 2. `processQueue()`



这是任务调度器，负责处理用户选中的论文列表。

- **作用**：依次生成摘要，而不是同时生成。
- **为什么不并发？**：大模型 API 通常有并发限制（例如每秒只能请求 1 次）。如果并发请求，会导致大量报错。
- **逻辑**：
  - 使用 `for` 循环处理选中的论文。
  - 调用 `getSummary` 获取摘要。
  - 调用 `displayResult` 渲染结果。
  - 每处理完一篇，`await sleep(2000)`（等待 2 秒），确保不触发 Moonshot 的限流。



#### 3. `getSummary(text)`



- **作用**：将论文摘要文本发送给 Worker 的 `/moonshot` 路由。
- **提示词 (Prompt Engineering)**：在代码中定义了 System Prompt：“你是一个专业的学术论文分析助手...”，确保 AI 输出格式统一（研究目的、方法、结论）。



#### 4. `debugLog(msg, type)`



- **作用**：在页面底部的灰色面板显示运行日志。
- **意义**：让用户知道程序“是否活着”，以及论文是因为什么原因（无摘要？日期不符？）被过滤掉的。这对排查“搜不到论文”的问题至关重要。

------



## 5. 使用指南与注意事项





### 如何部署



1. **Worker**: 将 `worker.js` 代码部署到 Cloudflare Workers，并在 Settings -> Variables 中添加 `MOONSHOT_API_KEY`。
2. **Frontend**: 修改 `index.html` 中的 `WORKER_URL` 为你的 Worker 地址，然后上传到 Cloudflare Pages。



### 常见问题排查



- **Q: 为什么搜不到最近几天的论文？**
  - A: Semantic Scholar 的数据库更新有延迟，通常需要几天到一周的时间收录。
- **Q: 搜索速度为什么变慢了？**
  - A: 为了防止 `429` 封锁，我们在 V3.0 版本中强制增加了请求间隔（每页间隔 4 秒）。这是为了稳定性做出的妥协。
- **Q: 调试日志显示 "Offset X 请求失败: 429"？**
  - A: 说明当前 IP 请求过频。程序会自动进入 10 秒冷却期并重试，通常不需要人工干预。