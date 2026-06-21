# AskUserQuestion 工具设计与使用指南

`AskUserQuestion` 是 Claude Code 中的核心交互工具之一。它允许大模型（LLM）从传统的纯文本问答模式，升级为高效的**结构化、卡片式多栏问答交互**。本文将从应用场景、设计模式、注意要点，以及前端配合与前端设计模式等方面，对该工具展开深入拆解。

---

## 一、 工具基本形态（选择题与填空问答混合机制）

该工具在交互形态上并不是纯粹的选择题，而是采用 **“选择题 + 自由文本” 的混合问答机制**，主要表现为以下特征：

1.  **单选与多选（选择题形态）**：
    *   调用该工具时，模型必须传入包含 2~4 个选项的 `options` 数组。
    *   通过 `multiSelect` 参数控制交互模式：设置 `false` 时为**单选题**（前端渲染为单选框）；设置 `true` 时为**多选题**（前端渲染为复选框，允许用户多选）。
2.  **自动补充的“其他”输入（填空问答形态）**：
    *   前端界面（无论是控制台 TUI 还是桌面 Web UI）在渲染该卡片时，会自动在问题选项下方渲染一个 **“自由文本输入框 (Textarea)”**，无需模型在 Schema 中声明。
    *   如果模型给出的所有预选选项都不符合用户意图，用户可以在文本输入框内输入自定义内容（相当于“其他：______”）。
    *   当用户开始在输入框内打字时，前端会自动取消所有已勾选的单选/多选状态，将自由文本作为最终答案返回。

---

## 二、 工具应用场景 (Application Scenarios)

`AskUserQuestion` 主要应用于模型在开发流程中遇到决策分支、不确定性或环境受限等场景：

1.  **模糊需求澄清**：当用户的指令过于宽泛、上下文不足或存在歧义时。例如，用户仅输入“帮我写个用户登录功能”，模型可以使用此工具让用户选择具体的认证机制（如 JWT、Session 或 OAuth2）。
2.  **技术方案与依赖权衡**：面临具有不同优缺点（如性能、包大小、维护成本）的代码实现或依赖包选择时。例如，在处理复杂时间格式化时，让用户在 `moment`（功能完整但偏重）与 `dayjs`（极致轻量）之间做出抉择。
3.  **测试策略与环境折中**：本地缺少执行环境（如 Docker）导致自动化测试失败，模型需向用户征求折中方案（如“忽略 E2E 测试仅跑单元测试”，或“协助用户安装本地 Docker”）。
4.  **重要重构的二次确认**：当重构影响较广、可能引入破坏性变更时，用于确认用户的接受度。

---

## 三、 工具端设计模式 (Tool Design Patterns)

在后端/引擎端，该工具的实现融合了多种经典设计模式，确保其高内聚、低耦合与安全性：

1.  **工厂模式 (Factory Pattern)**：
    *   通过 `buildTool(def)` 统一生成标准化的 Tool 实例。引擎定义了通用的 `TOOL_DEFAULTS`，子工具只需填入各自特有的 Schema、`call` 方法与渲染逻辑，极大地简化了新工具的扩展。
2.  **中断与异步解耦模式 (Interrupt & Loop Suspension)**：
    *   通过工具的 `checkPermissions` 方法返回 `behavior: 'ask'`，引擎会**挂起**当前大模型的 Agent 循环。控制权被交还给用户，等到用户在前端完成答题并回调触发 `respondToPermission` 后，引擎才将结果喂回给模型并恢复循环。
3.  **提示词与业务逻辑解耦模式 (Separation of Concerns)**：
    *   将长篇幅的 Markdown 格式说明书及 Preview 用法指南隔离在 `prompt.ts` 中，而 `AskUserQuestionTool.tsx` 仅专注参数验证（Zod Schema）与终端 UI 的渲染逻辑。
4.  **安全过滤器模式 (Filter/Sanitization)**：
    *   对于模型生成的预览富文本内容，使用 `validateInput` 进行安全审计，拦截包含危险 `<script>`、`<style>` 标签或全局 `<html>`/`<body>` 的 HTML 片段，保障客户端环境免受 XSS 攻击。

---

## 四、 工具端注意要点 (Tool Key Points)

开发或操作此工具时，模型与开发者需要遵循以下核心准则：

1.  **上下文长度控制与批处理 (Batching)**：
    *   提问数量限制在 1-4 个，每个问题选项限制在 2-4 个。模型必须在内部合并同类问题，尽量在一次提问中包含所有依赖细节，规避碎片化提问，防止因反复中断导致用户体验下降或 Prompt 缓存失效。
2.  **严禁替代计划批准 (Isolation from Plan Mode)**：
    *   在 Plan Mode 状态下，此工具仅限用于在生成计划前澄清需求。任何关于“计划是否可行”、“是否开始执行”的计划批准，**必须**调用专有的 `ExitPlanMode` 工具，绝对不能使用 `AskUserQuestion` 代替。
3.  **行动至上与规避无关紧要的细节 (Bias toward action)**：
    *   模型应当拥有自主解决问题的心态。对于常规的、可逆的代码改动或命名偏好，应当自行做出最佳决策并及时提交代码，避免因微小细节频频打扰用户。
4.  **推荐项前置规范**：
    *   如果模型认为某个技术方案更为优越，必须将其放在选项数组的第一个，且在 `label` 末尾追加 `(Recommended)` 标示。

---

## 五、 前端配合机制 (Frontend Coordination)

前端的配合是确保问卷卡片能与用户无缝交互的关键：

1.  **挂起拦截与权限接管**：
    *   当引擎收到大模型的 `AskUserQuestion` 调用并挂起时，前端（TUI 或 Desktop Web）会捕获这个 `pendingPermission` 事件，拦截通用的“同意/拒绝”交互，转而将问题参数解析为自定义的多选卡片。
2.  **双端自适应渲染 (Adaptive Rendering)**：
    *   **在 TUI（终端端）**：前端拦截标准输入，利用终端组件（React Ink）绑定键盘事件监听器，使用户可以通过键盘上下键移动高亮光标、空格键勾选、回车键提交。
    *   **在 Desktop/Web（网页端）**：前端解析问题数据，若发现有 `preview` 字段，会自动切分为**左边选项列表、右边富文本/代码预览框**的双栏对比布局。
3.  **状态机回调与恢复执行 (Callback Dispatch)**：
    *   一旦用户完成所有答题并点击“Submit”，前端会将勾选的值及用户手写输入（annotations）序列化为 `{ answers: Record<string, string> }`，调用 Store 暴露的 `respondToPermission(requestId, answers)` 行为。这会完成挂起阶段的回调，让本地执行引擎能够组装 `tool_result` 传输回 LLM。

---

## 六、 前端设计模式 (Frontend Design Patterns)

前端组件的交互和渲染架构运用了以下设计模式：

1.  **适配器模式/桥接模式 (Adapter/Bridge Pattern)**：
    *   定义了统一的 `Question` / `QuestionOption` 接口协议。前端分别为 CLI 终端环境（使用 React Ink 渲染 TUI）与 Electron 桌面环境（使用 CSS/HTML 渲染 Web UI）提供了适配器实现，保证了业务逻辑一次编写，双端自适应展示。
2.  **状态锁模式 / 单向数据流 (Immutable State/Lock Pattern)**：
    *   组件内部维护答题状态（`selections`、`freeTexts`）。一旦点击提交，立刻切换状态为 `submitted: true`，此时 UI 卡片透明度降低，禁用所有点击和输入事件，实现防重提交与不可逆操作。
3.  **主从视图联动模式 (Master-Detail Pattern)**：
    *   对于包含代码/配置预览的题目，用户在左侧选择/聚焦不同的选项（Master），右侧预览框（Detail）会实时重绘展现对应的代码片段或 ASCII UI 结构，极大地增强了视觉比对体验。
4.  **页签式组件导航 (Tabs Pattern)**：
    *   当传入多个问题时，前端动态引入标签页，未回答的页面有未完成标识，答完的页面自动打上勾选角标，将复杂的多步交互简化在单个卡片组件中。

---

## 七、 什么时候推荐 LLM 使用？ (LLM Recommended Usage)

*   **存在歧义的需求**：当用户提出的目标不明确，或代码库存在多种互斥实现路径时。
*   **依赖库与架构抉择**：引入第三方包时，需告知用户各自的特性并让其最终拍板。
*   **本地环境配置受限**：由于缺失本地权限、环境变量或测试工具，需用户提供折中意见时。
*   **Worker 协同的验证确认**：子代理完成重构，需要主进程用户确认如何测试验证。

---

## 八、 什么时候不推荐 LLM 使用？ (LLM Non-Recommended Usage)

*   **常规错误与文件缺失**：读写文件或运行命令报错时，模型应自主诊断（阅读类似代码、使用 glob/grep 定位），严禁以问卷形式将调试工作甩给用户。
*   **微小的设计偏好**：例如命名规范、普通变量声明、无硬性约束的细节重构，应当自行选定最佳实践，保持 Bias toward action。
*   **计划审批流程**：绝对不可用此工具去询问用户“方案是否合适”、“我可以开始了吗”，必须走 `ExitPlanMode`。
*   **碎片化重复提问**：严禁连续多轮发出极小的单个问题问卷，应通过批处理（Batching）一次性解决。

---

## 九、 完整的工具交互报文示例

### 1. LLM 发送的工具调用（Tool Use JSON）

```json
{
  "name": "AskUserQuestion",
  "id": "toolu_ask_user_001",
  "input": {
    "questions": [
      {
        "question": "Which HTTP client library should we adopt for the new API integration?",
        "header": "HTTP Client",
        "multiSelect": false,
        "options": [
          {
            "label": "axios",
            "description": "Promise based HTTP client with automatic JSON transform. (Recommended)",
            "preview": "```typescript\nimport axios from 'axios';\nconst response = await axios.get('/api/user');\nconsole.log(response.data);\n```"
          },
          {
            "label": "node-fetch",
            "description": "A light-weight module that brings window.fetch to Node.js.",
            "preview": "```typescript\nimport fetch from 'node-fetch';\nconst response = await fetch('/api/user');\nconst data = await response.json();\nconsole.log(data);\n```"
          }
        ]
      }
    ]
  }
}
```

### 2. 用户选择后的回调入参（Updated Input JSON）

用户在前端选中 `axios` 后提交：

```json
{
  "questions": [ ... ],
  "answers": {
    "Which HTTP client library should we adopt for the new API integration?": "axios"
  }
}
```

### 3. 最终返回给大模型的内容（Tool Result Content）

```markdown
User has answered your questions: "Which HTTP client library should we adopt for the new API integration?"="axios". You can now continue with the user's answers in mind.
```
