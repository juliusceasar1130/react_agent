# “轻量结构化输出” (Prompt 规约 + 前端轻改) 实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 贯彻“Prompt 规约 + 前端布局轻改”极简路线，优化大模型的数据呈现方式。通过限制大明细表打印并引导其输出 30 行内的小透视表，结合前端表格默认展开、表格紧跟LLM正文后面、术语/词典等辅助卡片置底等布局调整及时序防抖，消灭打字机延迟和视觉闪烁抖动。

**Architecture:** 
1. **Prompt 改版**：在 `base_system_prompt.md` §4.4 中加入明细与统计意图分流规则。按明细类（禁止正文打表）、分析统计类（允许 30 行内汇总表及深度归因分析）、开放问答类（无限制富文本 Markdown 回答）三大提问意图进行精确的格式分流。
2. **前端轻改**：
   * 将 `MessageItem.vue` 中渲染的折叠卡片与数据表重排布：将“参考业务术语”、“参考数据库物理字典”卡片移动到气泡最底部；将“SQL 查询结果”数据预览表格上移到紧邻 AI 文本正文下方并配置默认展开 `open` 贴合。
   * **Layout Shift 防抖动**：当侧信道数据先到，AI 文本 Token 尚未吐出 (`isStreamingActive && !content`) 时，在正文区渲染脉冲骨架屏 (Skeleton) 占位，消灭页面的闪烁跳动。
   * **语义化标题 H3 样式美化**：在 `style.css` 中为 `.message-markdown h3` 增加左侧青色 3px 竖线和 padding 缩进，实现符合最佳实践的精美语义化标题渲染。

**Tech Stack:** Vue 3, Vanilla CSS, Python 3.12 (Prompt Config)

---

### Task 1: 系统提示词 (Prompt) 规约调整

**Files:**
- Modify: `backend/app/agent/prompts/base_system_prompt.md:186-194`
- Test: 创建轻量脚本验证词条存在性

- [ ] **Step 1: 编写检查脚本 (TDD 替代)**
  在 `<appDataDir>\brain\<conversation-id>/scratch/` 目录下创建临时验证脚本 `verify_prompt_rule.py`：
  ```python
  import pathlib

  prompt_path = pathlib.Path(r"f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent-llamaindex-rag\backend\app\agent\prompts\base_system_prompt.md")
  content = prompt_path.read_text(encoding="utf-8")

  # 验证是否删除了旧规约，且新增了分流及 30 行限制规约
  assert "若常规查询结果，以 Markdown 表格呈现" not in content
  assert "明细类查询" in content
  assert "统计/对比类查询" in content
  assert "限制在 30 行以内" in content
  assert "开放问题与知识问答类" in content
  print("PROMPT RULES VERIFIED SUCCESS")
  ```

- [ ] **Step 2: 运行验证脚本确认失败**
  运行：`D:\000_software_install\miniconda3\envs\py312_agent\python.exe C:\Users\julius\.gemini\antigravity-ide\brain\aa8625c1-10fb-46a6-b247-e9355f434d87/scratch/verify_prompt_rule.py`
  预期输出：AssertionError 报错（旧规则仍存在）。

- [ ] **Step 3: 修改 base_system_prompt.md 的格式规范**
  将 [base_system_prompt.md:186-194](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/prompts/base_system_prompt.md#L186-L194) 的旧打表条款：
  ```markdown
  - 若常规查询结果，以 Markdown 表格呈现，表头使用字段中文名（如 skill 中定义），后附：
    1. 总行数（若被截断，标注"部分结果，共N行"）。
    2. 关键数据口径说明（如"NV数量=缺陷数×单车缺陷系数"）。
  - 若包含 SQL，代码单独放在 ```sql 代码块中，禁止与解释文字混排。
  - 调用工具时，严格使用工具要求的参数结构。例如 build_chart_artifact 中 series 数组内每个对象仅含允许的 6 个键，且 category_field/category_value 必须成对出现。
  - 多步骤任务：每完成一步，用单行简要标注当前状态，例如：
    > 已加载paint_shop技能，确认表T_QM_DEFECT存在字段DEFECT_CODE。
    禁止在步骤标注中展开详细解释——解释留到最后统一给出。
  ```
  改写为“按用户提问意图精确进行格式分流规约”：
  最终回复的呈现格式必须根据用户提问意图进行精确的格式分流：
  ```markdown
  - 最终回复的呈现格式必须根据用户提问意图进行精确的格式分流：
    1. **数据明细查询类**（用户问"明细/列表/有哪些/车辆清单"）：正文**禁止**输出任何明细大表，字数压缩在 150 字或 3 行以内，只提供极其精炼的数目概述（如“已为您查询到喷漆车间在制车共 12 台，最早进站时间 14:32”），明细数据完全由正下方的系统交互卡片渲染。
    2. **数据分析与统计对比类**（用户问"统计/对比/排名/占比/趋势分析/为什么"）：正文可输出高信息密度的**汇总透视表**（通常为 2~10 行，限制在 30 行以内，如分类 GROUP BY 表、Top N 等）。若分类过多逼近上限，应改用更粗粒度分组或只给定性结论，禁止自行做“Top3+其它”式二次聚合（属 LLM 派生计算，放大数值纪律风险）。同时应在正文提供有深度的归因诊断与洞察结论，行数不受极简限制。表头使用字段中文名。
    3. **开放问题与知识问答类**（用户问"术语解释/如何计算/说明"等，未查询数据库）：采用标准的**富文本 Markdown 回答**，完全不受字数或行数限制，确保专业术语的解释深度、公式推导与背景说明完整度。
  ```
  - 若包含 SQL，代码单独放在 ```sql 代码块中，禁止与解释文字混排。
  - 调用工具时，严格使用工具要求的参数结构。例如 build_chart_artifact 中 series 数组内每个对象仅含允许的 6 个键，且 category_field/category_value 必须成对出现。
  - 多步骤任务：每完成一步，用单行简要标注当前状态，例如：
    > 已加载paint_shop技能，确认表T_QM_DEFECT存在字段DEFECT_CODE。
    禁止在步骤标注中展开详细解释——解释留到最后统一给出。
  ```

- [ ] **Step 4: 重新运行验证脚本验证通过**
  运行：`D:\000_software_install\miniconda3\envs\py312_agent\python.exe C:\Users\julius\.gemini\antigravity-ide\brain\aa8625c1-10fb-46a6-b247-e9355f434d87/scratch/verify_prompt_rule.py`
  预期输出：`PROMPT RULES VERIFIED SUCCESS`。

- [ ] **Step 5: 物理删除临时 verify 脚本**

---

### Task 2: 前端 MessageItem.vue 表格默认展开、Layout Shift 骨架防抖与 H3/H4 样式美化

**Files:**
- Modify: `frontend/src/components/MessageItem.vue:28-39`、`L331`
- Modify: `frontend/src/style.css:241`

- [ ] **Step 1: 修改表格 details 节点为默认展开**
  将 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/MessageItem.vue) 处的 `details` 标签修改为默认展开 `open`：
  ```html
  <details open class="group rounded-[24px] border border-neutral-200/80 bg-neutral-50/50 p-3.5 shadow-sm transition-all duration-200">
  ```

- [ ] **Step 1.5: 重新调整前端卡片节点顺序 (业务术语与物理词典置底，SQL结果置前)**
  修改 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/MessageItem.vue)，将 `parsedRagContext` (参考业务术语) 和 `parsedLexiconContext` (参考物理词典) 两个块剪切并物理移动至 Chart/CSV 模块之后，操作反馈按钮栏之前。确认 SQL 查询结果紧跟在文本正文下方。

- [ ] **Step 2: 增加流式骨架屏防 Layout Shift 闪烁抖动**
  修改 [MessageItem.vue:28-39](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/MessageItem.vue#L28-L39) AI 正文流式渲染块：
  ...
- [ ] **Step 3: 增加 style.css 中 H3 语义化小标题的左竖线美化**
  在 [style.css](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/style.css) 末尾追加：
  ```css
  .message-markdown h3 {
    border-left: 3px solid rgb(20 184 166);
    padding-left: 0.55rem;
    font-size: 0.95rem;
    font-weight: 600;
    color: rgb(30 41 59);
    margin-top: 1.2rem;
    margin-bottom: 0.6rem;
  }
  ```
  ```html
          <p
            v-if="isUser || isStreamingActive"
            class="whitespace-pre-wrap break-words text-[15px] leading-7"
            :class="textClass"
          >
            <template v-if="isStreamingActive">
              {{ content }}
              <span class="cursor-blink"></span>
            </template>
            <template v-else>
              {{ content }}
            </template>
          </p>
  ```
  改写为若 `content` 尚为空则渲染微动骨架屏：
  ```html
          <p
            v-if="isUser || isStreamingActive"
            class="whitespace-pre-wrap break-words text-[15px] leading-7"
            :class="textClass"
          >
            <template v-if="isStreamingActive">
              <span v-if="!content" class="flex flex-col gap-2 w-full animate-pulse my-2">
                <span class="h-3.5 bg-neutral-200/80 rounded-md w-2/3"></span>
                <span class="h-3.5 bg-neutral-200/60 rounded-md w-1/2"></span>
              </span>
              <span v-else>{{ content }}</span>
              <span class="cursor-blink"></span>
            </template>
            <template v-else>
              {{ content }}
            </template>
          </p>
  ```

- [ ] **Step 3: 前端 CSS 样式美化 h3/h4 (语义化最佳实践)**
  在 [style.css:241](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/style.css#L241) 处的 `.message-markdown blockquote` 样式下方，新增对 `h3` 和 `h4` 标题的左侧 Teal 竖线美化配置，使其不依赖 blockquote 即可在语义正确的标题上渲染侧竖线装饰。
  ```css
  .message-markdown h3,
  .message-markdown h4 {
    display: flex;
    align-items: center;
    border-left: 3px solid rgb(20 184 166 / 0.8);
    background: linear-gradient(180deg, rgb(20 184 166 / 0.05), rgb(241 245 249 / 0.3));
    padding: 0.45rem 0.75rem;
    color: rgb(30 41 59);
    border-radius: 0.5rem;
    font-size: 0.95rem;
    font-weight: 600;
    margin-top: 1.25rem;
    margin-bottom: 0.6rem;
  }
  ```

---

## 4. 验证方案

1. **编译运行验证**：
   * 启动前端开发服务器 `npm run dev` 确保 Vue 组件编译无差错。
   * 进行一次常规 SQL 明细查询（如“查询今天的在制明细”），验证 AI 文本不输出大 Markdown 表格，下方明细卡片直接 open 展开。
   * 进行一次统计聚合查询（如“统计今天的车型分布”），验证 AI 能够输出 30 行以内的汇总表，数据与下方明细底座相吻合。
   * 观察流式开始瞬间，是否有骨架屏占位，随后 AI 文本流畅吐出，Layout Shift 闪跳感消失。同时，AI 回复中的标题（h3/h4）应自动渲染出高亮竖线装饰卡片，且没有 blockquote 语意漂移。
2. **自动化测试回归**：
   * 执行全量 29 项测试确保 regression 一致：
     `pytest backend/app/agent/tools/test_csv_export_command.py backend/app/agent/tools/test_chart_artifact_command.py backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`