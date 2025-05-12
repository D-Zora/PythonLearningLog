from langchain_core.messages import AIMessage
from typing import Dict, Any
import logging
from ...classes import ResearchState
from .base import BaseResearcher

logger = logging.getLogger(__name__)

class FinancialAnalyst(BaseResearcher):
    def __init__(self, use_local_data: bool = True) -> None:
        # 模式切换说明：
        # - use_local_data=True: 使用本地数据模式（用于测试）
        # - use_local_data=False: 使用 Tavily API 模式（用于生产环境）
        # 注意：本地数据模式下，需要在 local_data/{company_name}/ 目录下有对应的 JSON 文件
        super().__init__(use_local_data=use_local_data)
        self.analyst_type = "financial_analyst"

    async def analyze(self, state: ResearchState) -> Dict[str, Any]:
        company = state.get('company', 'Unknown Company')
        websocket_manager = state.get('websocket_manager')
        job_id = state.get('job_id')
        
        try:
            # 生成搜索查询（本地数据和 API 模式都使用相同的查询生成逻辑）
            queries = await self.generate_queries(
                state,
                """
                Generate queries on the financial analysis of {company} in the {industry} industry such as:
                - Fundraising history and valuation
                - Financial statements and key metrics
                - Revenue and profit sources
                """)
            
            # 添加查询消息（本地数据和 API 模式都显示相同的查询信息）
            subqueries_msg = "🔍 Subqueries for financial analysis:\n" + "\n".join([f"• {query}" for query in queries])
            messages = state.get('messages', [])
            messages.append(AIMessage(content=subqueries_msg))
            state['messages'] = messages

            # 发送查询状态更新（本地数据和 API 模式都使用相同的状态更新逻辑）
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message=f"Financial analysis queries generated",
                    result={
                        "step": "Financial Analyst",
                        "analyst_type": "Financial Analyst",
                        "queries": queries,
                        "mode": "local_data" if self.use_local_data else "tavily_api"  # 添加模式信息
                    }
                )
            
            # 处理网站抓取数据（本地数据和 API 模式都支持）
            financial_data = {}
            if site_scrape := state.get('site_scrape'):
                company_url = state.get('company_url', 'company-website')
                financial_data[company_url] = {
                    'title': state.get('company', 'Unknown Company'),
                    'raw_content': site_scrape,
                    'query': f'Financial information on {company}'
                }

            # 执行搜索（根据模式自动选择本地数据或 API）
            for query in queries:
                documents = await self.search_documents(state, [query])
                for url, doc in documents.items():
                    doc['query'] = query
                    financial_data[url] = doc

            # 最终状态更新（本地数据和 API 模式使用相同的状态更新逻辑）
            completion_msg = f"Completed analysis with {len(financial_data)} documents using {'local data' if self.use_local_data else 'Tavily API'}"
            
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message=completion_msg,
                    result={
                        "step": "Searching",
                        "analyst_type": "Financial Analyst",
                        "queries": queries,
                        "mode": "local_data" if self.use_local_data else "tavily_api",  # 添加模式信息
                        "documents_found": len(financial_data)
                    }
                )
            
            # 更新状态（本地数据和 API 模式使用相同的数据结构）
            messages.append(AIMessage(content=completion_msg))
            state['messages'] = messages
            state['financial_data'] = financial_data

            return {
                'message': completion_msg,
                'financial_data': financial_data,
                'analyst_type': self.analyst_type,
                'queries': queries
            }

        except Exception as e:
            error_msg = f"Financial analysis failed: {str(e)}"
            # 发送错误状态（本地数据和 API 模式使用相同的错误处理逻辑）
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="error",
                    message=error_msg,
                    result={
                        "analyst_type": "Financial Analyst",
                        "error": str(e),
                        "mode": "local_data" if self.use_local_data else "tavily_api"  # 添加模式信息
                    }
                )
            raise  # 重新抛出异常以保持错误流程

    async def run(self, state: ResearchState) -> Dict[str, Any]:
        return await self.analyze(state)