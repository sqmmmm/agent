from tools.search import search_web, search_arxiv
from tools.knowledge import search_knowledge_base
from tools.file_ops import save_report, list_reports

# 所有可用工具
ALL_TOOLS = [
    search_web,
    search_arxiv,
    search_knowledge_base,
    save_report,
    list_reports,
]
