from langchain_core.messages import AIMessage
from typing import Dict, Any
from ...classes import ResearchState
from .base import BaseResearcher

class IndustryAnalyzer(BaseResearcher):
    def __init__(self, use_local_data: bool = True) -> None:
        # 模式切换说明：
        # - use_local_data=True: 使用本地数据模式（用于测试）
        # - use_local_data=False: 使用 Tavily API 模式（用于生产环境）
        # 注意：本地数据模式下，需要在 local_data/{company_name}/ 目录下有对应的 JSON 文件
        super().__init__(use_local_data=use_local_data)
        self.analyst_type = "industry_analyzer"

    async def analyze(self, state: ResearchState) -> Dict[str, Any]:
        company = state.get('company', 'Unknown Company')
        industry = state.get('industry', 'Unknown Industry')
        msg = [f"🏭 Industry Analyzer analyzing {company} in {industry}"]
        
        # 生成搜索查询（本地数据和 API 模式都使用相同的查询生成逻辑）
        queries = await self.generate_queries(state, """
        Generate queries on the industry analysis of {company} in the {industry} industry such as:
        - Market position
        - Competitors
        - {industry} industry trends and challenges
        - Market size and growth
        """)

        # 添加查询消息（本地数据和 API 模式都显示相同的查询信息）
        subqueries_msg = "🔍 Subqueries for industry analysis:\n" + "\n".join([f"• {query}" for query in queries])
        messages = state.get('messages', [])
        messages.append(AIMessage(content=subqueries_msg))
        state['messages'] = messages

        # 发送查询状态更新（本地数据和 API 模式都使用相同的状态更新逻辑）
        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message=f"Industry analysis queries generated",
                    result={
                        "step": "Industry Analyst",
                        "analyst_type": "Industry Analyst",
                        "queries": queries,
                        "mode": "local_data" if self.use_local_data else "tavily_api"  # 添加模式信息
                    }
                )
        
        industry_data = {}
        
        # 处理网站抓取数据（本地数据和 API 模式都支持）
        if site_scrape := state.get('site_scrape'):
            msg.append("\n📊 Including site scrape data in company analysis...")
            company_url = state.get('company_url', 'company-website')
            industry_data[company_url] = {
                'title': state.get('company', 'Unknown Company'),
                'raw_content': site_scrape,
                'query': f'Industry analysis on {company}'
            }
        
        # 执行搜索（根据模式自动选择本地数据或 API）
        try:
            for query in queries:
                documents = await self.search_documents(state, [query])
                if documents:
                    for url, doc in documents.items():
                        doc['query'] = query
                        industry_data[url] = doc
            
            msg.append(f"\n✓ Found {len(industry_data)} documents")
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message=f"Found {len(industry_data)} documents using {'local data' if self.use_local_data else 'Tavily API'}",
                        result={
                            "step": "Searching",
                            "analyst_type": "Industry Analyst",
                            "queries": queries,
                            "mode": "local_data" if self.use_local_data else "tavily_api"  # 添加模式信息
                        }
                    )
        except Exception as e:
            msg.append(f"\n⚠️ Error during research: {str(e)}")
        
        # 更新状态（本地数据和 API 模式使用相同的数据结构）
        messages = state.get('messages', [])
        messages.append(AIMessage(content="\n".join(msg)))
        state['messages'] = messages
        state['industry_data'] = industry_data
        
        return {
            'message': msg,
            'industry_data': industry_data
        }

    async def run(self, state: ResearchState) -> Dict[str, Any]:
        return await self.analyze(state) 