# 智能研究助手项目工程化分析

## 一、项目概述

### 1.1 项目定位

**智能研究助手（Smart Research Assistant）** 是一个基于 LangGraph 构建的 AI Agent 系统，集成了 Web 搜索、本地知识库（RAG）、多 Agent 协作和质量审查循环，能够对用户问题进行分类、研究、分析并生成结构化报告。

### 1.2 核心能力

- **问题分类路由**：自动识别简单问题、研究型问题、需要深度报告的问题
- **Web 搜索**：通过 Tavily 搜索引擎获取最新网络信息
- **学术论文检索**：通过 arXiv API 搜索学术论文
- **本地知识库 RAG**：基于 Chroma 向量数据库的语义检索
- **多 Agent 协作**：Researcher → Analyst → Writer 三阶段流水线
- **质量审查循环**：报告生成后经 LLM 审查，未通过则返回研究节点迭代
- **多轮对话记忆**：基于 MemorySaver 的会话持久化

---

## 二、整体架构

### 2.1 技术栈

| 层次 | 技术选型 | 用途 |
|------|---------|------|
| LLM 底座 | ModelScope Qwen (Qwen3.5-35B-A3B) | 统一推理引擎 |
| 向量数据库 | Chroma | 本地知识库向量存储 |
| Embedding | 阿里云 DashScope MaaS API | 文本向量化 |
| 搜索 | Tavily API + arXiv API | 网络与学术信息获取 |
| 工作流框架 | LangGraph | 状态图构建、路由、循环、持久化 |
| 日志监控 | Python logging + 自定义装饰器 | 节点/工具执行跟踪 |
| 配置管理 | dotenv (.env) | API Key 与模型参数管理 |

### 2.2 目录结构

```
pro2/
├── main.py                  # 应用入口（交互式/单次查询模式）
├── state.py                 # ResearchState 定义（全局状态 schema）
├── graph.py                 # LangGraph 工作流定义（节点+边+编译）
├── mylogger.py              # 日志装饰器（节点/工具执行耗时记录）
├── mycallback.py            # LangChain 回调处理器（LLM/工具执行监控）
├── requirements.txt        # 依赖清单
├── readme.md               # 项目说明文档
├── .env                    # 环境变量配置（API Keys）
│
├── agents/                 # Agent 节点实现
│   ├── __init__.py         # ALL_AGENTS 导出
│   ├── researcher.py       # 研究节点（搜索结果+知识库 → 研究笔记）
│   ├── analyst.py          # 分析节点（研究笔记 → 深度分析）
│   └── writer.py           # 写作节点（分析 → 结构化报告，含 Pydantic 输出解析）
│
└── tools/                  # LangGraph 工具集
    ├── __init__.py         # ALL_TOOLS 导出
    ├── search.py            # search_web / search_arxiv
    ├── knowledge.py         # search_knowledge_base（RAG 检索）
    └── file_ops.py         # save_report / list_reports
```

---

## 三、核心数据结构

### 3.1 ResearchState — 贯穿工作流的全局状态

定义于 `state.py`，是整个 LangGraph 的状态 schema：

```python
class ResearchState(TypedDict):
    # 对话
    messages: Annotated[list, add_messages]   # 消息历史（add_messages 装饰器支持追加）

    # 研究过程
    question: str              # 原始问题
    question_type: str        # 问题类型：simple / research / report
    search_results: str       # 工具搜索结果
    knowledge_results: str    # 知识库检索结果
    research_notes: str       # 研究笔记
    analysis: str             # 分析结果
    report: str               # 最终报告

    # 控制流
    iteration: int            # 当前审查迭代次数
    review_passed: bool      # 质量审查是否通过
    review_feedback: str     # 审查反馈
    next_agent: str          # 下一个 agent（预留）
```

**状态流转特点**：`messages` 字段使用 `Annotated[list, add_messages]`，使消息在节点间自动追加而非覆盖；其他字段由各节点按需写入。

---

## 四、工作流图详解

### 4.1 图的节点定义

| 节点名 | 实现文件 | 职责 |
|--------|---------|------|
| `classify` | `graph.py::classify_question` | LLM 判断问题类型（simple/research/report） |
| `simple_answer` | `graph.py::simple_answer` | 直接用 LLM 回答简单问题 |
| `tool_calling` | `graph.py::tool_calling_node` | LLM 决定调用哪些工具（search_web / search_arxiv / search_knowledge_base） |
| `tool_executor` | `graph.py::ToolNode(ALL_TOOLS)` | LangGraph 内置工具执行节点 |
| `collect` | `graph.py::collect_results` | 收集工具返回的 ToolMessage |
| `researcher` | `agents/researcher.py::researcher_node` | 整理搜索+知识库结果，输出研究笔记 |
| `analyst` | `agents/analyst.py::analyst_node` | 深度分析研究笔记，输出分析报告 |
| `writer` | `agents/writer.py::writer_node` | 生成结构化 Markdown 报告（含 Pydantic 解析） |
| `review` | `graph.py::review_node` | 质量审查（3次迭代内未通过则打回） |

### 4.2 边的连接关系

```
START
  │
  ▼
classify ──(simple)──→ simple_answer ──────────────────────────→ END
  │
  │(research/report)
  ▼
tool_calling ──(有tool_calls)──→ tool_executor ──→ collect
  │(无tool_calls)                                      │
  └────────────────────────────────────────────────────┤
                                                       ▼
                                                   researcher
                                                       │
                                                       ▼
                                                    analyst
                                                       │
                                                       ▼
                                                    writer
                                                       │
                                                       ▼
                                                    review
                                                       │
                                          ┌────────────┴───────────┐
                                     (通过)│                    │(未通过)
                                          ▼                    ▼
                                         END              researcher
                                                          (循环)
```

### 4.3 条件路由函数

| 路由函数 | 判断逻辑 | 目标 |
|---------|---------|------|
| `route_by_type` | `question_type == "simple"` | `"simple_answer"` |
| | 否则 | `"tool_calling"` |
| `route_after_tools` | 最后一条消息有 `tool_calls` | `"tool_executor"` |
| | 否则 | `"collect"` |
| `route_after_review` | `review_passed == True` | `END` |
| | 否则 | `"researcher"` |

---

## 五、工具层（Tools）

定义于 `tools/__init__.py`，统一注册为 `ALL_TOOLS` 列表，供 `ToolNode` 和 `tool_calling_node` 绑定使用。

### 5.1 工具清单

| 工具名 | 函数 | 功能 |
|-------|------|------|
| `search_web` | `tools/search.py` | Tavily 高级搜索（返回综合答案 + 5条结果 + 评分） |
| `search_arxiv` | `tools/search.py` | arXiv 学术论文搜索（返回标题 + 摘要） |
| `search_knowledge_base` | `tools/knowledge.py` | Chroma 向量库 RAG 检索（k=4） |
| `save_report` | `tools/file_ops.py` | 将 Markdown 内容保存到 `./data/reports/` |
| `list_reports` | `tools/file_ops.py` | 列出已保存的报告文件 |

### 5.2 RAG 知识库构建流程

`tools/knowledge.py` 中的 `build_vector_store` 函数：

1. **加载文档**：`DirectoryLoader` 扫描 `./data/knowledge/**/*.md`
2. **文档切分**：`RecursiveCharacterTextSplitter`（chunk_size=500, overlap=50）
3. **向量化**：`MaaSEmbeddings` 调用 DashScope API（每批 ≤10 条）
4. **持久化存储**：Chroma 保存至 `./data/vector_store/`

单例模式 `_get_retriever()` 保证检索器全局复用。

---

## 六、Agent 层（Agents）

### 6.1 Researcher Agent — `agents/researcher.py`

**输入**：原始问题 + 搜索结果（search_results）+ 知识库结果（knowledge_results）

**输出**：`research_notes`

**实现**：LCEL 管道 `prompt | llm`，Prompt 要求输出带来源评估的研究笔记。

### 6.2 Analyst Agent — `agents/analyst.py`

**输入**：原始问题 + 研究笔记

**输出**：`analysis`

**实现**：LCEL 管道 `prompt | llm`，Prompt 要求进行深度分析（核心观点、趋势模式、专业见解）。

### 6.3 Writer Agent — `agents/writer.py`

**输入**：原始问题 + 研究笔记 + 分析结果

**输出**：`report`（Markdown 格式）

**实现**：LCEL 管道 `prompt | llm | PydanticOutputParser`，主路径用 Pydantic 模型 `ResearchReport`（title/summary/key_findings/detailed_analysis/conclusion/references）强制结构化输出；解析失败时降级为纯文本。

---

## 七、监控与日志

### 7.1 `mylogger.py` — 节点执行日志装饰器

`log_node_execution(node_name)`：装饰在每个节点函数上，记录：
- 执行开始时间
- 耗时（秒）
- 输出 key-value 摘要（字符串长度、列表项数）

`log_tool_execution(node_name)`：同理，记录工具执行。

### 7.2 `mycallback.py` — LangChain 回调处理器

`ResearchCallbackHandler` 继承 `BaseCallbackHandler`，监听：
- `on_llm_start` / `on_llm_end`：记录 LLM 输入输出
- `on_tool_start` / `on_tool_end`：记录工具调用与结果
- `on_chain_error`：记录链错误

---

## 八、入口与运行模式

### 8.1 `main.py`

```python
# 单次查询模式
python main.py "RAG是什么"

# 交互式模式
python main.py
```

两种模式均调用 `build_graph()` 编译图，通过 `graph.invoke()` 执行。

### 8.2 `graph.py::build_graph()`

1. 创建 `StateGraph(ResearchState)`
2. 添加 9 个节点（含内置 `ToolNode`）
3. 添加边和条件路由
4. 使用 `MemorySaver`（内存持久化 checkpointer）编译
5. 返回编译后的 `graph` 对象

---

## 九、模块间依赖关系图

```
main.py
  └── build_graph()          [入口启动时调用一次]
        │
        ├── state.py          [ResearchState 类型定义]
        ├── agents/
        │   ├── researcher.py ──→ state.py, mylogger.py, mycallback.py
        │   ├── analyst.py   ──→ state.py, mylogger.py, mycallback.py
        │   └── writer.py    ──→ state.py, mylogger.py, Pydantic
        ├── tools/
        │   ├── search.py    ──→ mylogger.py, Tavily/httpx
        │   ├── knowledge.py ──→ mylogger.py, Chroma, MaaSEmbeddings
        │   └── file_ops.py
        ├── mylogger.py      [纯工具模块，无外部依赖]
        ├── mycallback.py    ──→ logging
        └── dotenv/.env      [配置注入]

运行时消息流:
  User Input → messages (add_messages) → classify → simple/research/report 分流
                                              ↓
                            tool_calling → tool_executor → collect
                                              ↓
                            researcher → analyst → writer → review
                                              ↓
                               (未通过) → researcher (循环)
                               (通过) → END → report 输出
```

---

## 十、工程化设计亮点

| 维度 | 设计 |
|------|------|
| **状态管理** | `TypedDict` + `add_messages` 注解，类型安全且支持消息追加 |
| **工具注册** | `ALL_TOOLS` 集中注册，`ToolNode` 统一执行，解耦工具定义与调用 |
| **LCEL 管道** | `prompt \| llm \| parser` 模式，Prompt 模板与模型绑定清晰 |
| **日志切面** | 装饰器模式（AOP），在不修改业务逻辑的前提下注入监控 |
| **RAG 单例** | `_get_retriever()` 全局缓存向量检索器，避免重复连接 |
| **降级策略** | Writer 的 Pydantic 解析失败时自动降级到纯文本生成 |
| **审查循环** | 迭代计数上限（≥3次强制通过），防止死循环 |
| **多轮记忆** | `MemorySaver` checkpointer 支持 thread_id 隔离会话 |

---

## 十一、潜在改进建议

1. **Agent 抽象层**：三个 Agent（researcher/analyst/writer）有大量重复的 LLM 初始化代码，可抽象基类或工厂函数
2. **配置外部化**：`ALL_TOOLS` 和 `ALL_AGENTS` 可移至配置文件，实现动态注册
3. **错误处理**：当前节点函数无显式异常捕获，图级别的错误边界可加强
4. **向量数据库切换**：`Chroma` 硬编码，可抽象为 `VectorStore` 接口以支持 Milvus/Pinecone 等
5. **评估指标**：`review_node` 的审查标准单一，可引入 RAGAS 等量化评估指标
