"""State定义：贯穿整个工作流的核心数据结构"""

from typing import TypedDict, Annotated  # 定义状态字典的结构和类型提示
from langgraph.graph.message import add_messages  # 用于添加信息到状态中的装饰器

class ResearchState(TypedDict):
    """研究助手的全局状态"""

    # 对话
    messages: Annotated[list, add_messages]  # 消息历史  （add_messages 装饰器支持追加）

    # 研究过程
    question: str  # 原始问题
    question_type: str  # 问题类型： simple, research,report
    search_results: str  # 搜索结果
    knowledge_results: str  # 知识库检索结果
    research_notes: str    # 研究笔记
    analysis: str   # 分析结果
    report: str  # 最终报告

    # 控制
    iteration: int  # 当前迭代次数
    review_passed: bool  # 质量审查是否通过
    review_feedback: str  # 质量审查反馈
    next_agent: str    # 下一个agent
