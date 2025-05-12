from typing import TypedDict, NotRequired, Required, Dict, List, Any
from backend.services.websocket_manager import WebSocketManager

# 定义输入状态
class InputState(TypedDict, total=False):
    company: Required[str]
    company_url: NotRequired[str]
    hq_location: NotRequired[str]
    industry: NotRequired[str]
    websocket_manager: NotRequired[WebSocketManager]
    job_id: NotRequired[str]

# 定义研究状态
class ResearchState(InputState):
    site_scrape: Dict[str, Any]
    messages: List[Any]
    financial_data: Dict[str, Any]
    news_data: Dict[str, Any]
    industry_data: Dict[str, Any]
    company_data: Dict[str, Any]
    curated_financial_data: Dict[str, Any]
    curated_news_data: Dict[str, Any]
    curated_industry_data: Dict[str, Any]
    curated_company_data: Dict[str, Any]
    financial_briefing: str
    news_briefing: str
    industry_briefing: str
    company_briefing: str
    references: List[str]
    briefings: Dict[str, Any]
    report: str