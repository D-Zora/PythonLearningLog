import os
from datetime import datetime
from openai import AsyncOpenAI
from tavily import AsyncTavilyClient
from ...classes import ResearchState
from typing import Dict, Any, List
import logging
from ...utils.references import clean_title
from ...utils.local_data import LocalDataManager
from ...utils.text_reference_linker import TextReferenceLinker
import asyncio

logger = logging.getLogger(__name__)

class BaseResearcher:
    def __init__(self, use_local_data: bool = True):  # 默认使用本地数据模式
        # 切换模式：True 使用本地数据，False 使用 Tavily API
        # self.use_local_data = True  # 测试时使用本地数据模式
        # self.use_local_data = False  # 生产环境使用 Tavily API 模式
        # 使用传入的 use_local_data 参数
        self.use_local_data = use_local_data
        
        # 初始化数据管理器和文本链接器
        self.local_data_manager = LocalDataManager()
        self.text_linker = TextReferenceLinker()
        
        # Tavily API 配置（生产环境使用）
        # tavily_key = os.getenv("TAVILY_API_KEY")
        # if not tavily_key:
        #     raise ValueError("TAVILY_API_KEY environment variable is not set")
        # self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
        if not self.use_local_data:
            tavily_key = os.getenv("TAVILY_API_KEY")
            if not tavily_key:
                raise ValueError("TAVILY_API_KEY environment variable is not set")
            self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
            
        # OpenAI API 配置
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.openai_client = AsyncOpenAI(api_key=openai_key, base_url="https://openrouter.ai/api/v1")
        self.analyst_type = "base_researcher"

    @property
    def analyst_type(self) -> str:
        if not hasattr(self, '_analyst_type'):
            raise ValueError("Analyst type not set by subclass")
        return self._analyst_type

    @analyst_type.setter
    def analyst_type(self, value: str):
        self._analyst_type = value

    async def generate_queries(self, state: Dict, prompt: str) -> List[str]:
        company = state.get("company", "Unknown Company")
        industry = state.get("industry", "Unknown Industry")
        hq = state.get("hq", "Unknown HQ")
        current_year = datetime.now().year
        websocket_manager = state.get('websocket_manager')
        job_id = state.get('job_id')
        
        try:
            logger.info(f"Generating queries for {company} as {self.analyst_type}")
            
            response = await self.openai_client.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are researching {company}, a company in the {industry} industry."
                    },
                    {
                        "role": "user",
                        "content": f"""Researching {company} on {datetime.now().strftime("%B %d, %Y")}.
{self._format_query_prompt(prompt, company, hq, current_year)}"""
                    }
                ],
                temperature=0,
                max_tokens=4096,
                stream=True
            )
            
            queries = []
            current_query = ""
            current_query_number = 1

            async for chunk in response:
                if chunk.choices[0].finish_reason == "stop":
                    break
                    
                content = chunk.choices[0].delta.content
                if content:
                    current_query += content
                    
                    # Stream the current state to the UI.
                    if websocket_manager and job_id:
                        await websocket_manager.send_status_update(
                            job_id=job_id,
                            status="query_generating",
                            message="Generating research query",
                            result={
                                "query": current_query,
                                "query_number": current_query_number,
                                "category": self.analyst_type,
                                "is_complete": False
                            }
                        )
                    
                    # If a newline is detected, treat it as a complete query.
                    if '\n' in current_query:
                        parts = current_query.split('\n')
                        current_query = parts[-1]  # The last part is the start of the next query.
                        
                        for query in parts[:-1]:
                            query = query.strip()
                            if query:
                                queries.append(query)
                                if websocket_manager and job_id:
                                    await websocket_manager.send_status_update(
                                        job_id=job_id,
                                        status="query_generated",
                                        message="Generated new research query",
                                        result={
                                            "query": query,
                                            "query_number": len(queries),
                                            "category": self.analyst_type,
                                            "is_complete": True
                                        }
                                    )
                                current_query_number += 1

            # Add any remaining query (even if not newline terminated)
            if current_query.strip():
                query = current_query.strip()
                queries.append(query)
                if websocket_manager and job_id:
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="query_generated",
                        message="Generated final research query",
                        result={
                            "query": query,
                            "query_number": len(queries),
                            "category": self.analyst_type,
                            "is_complete": True
                        }
                    )
                current_query_number += 1
            
            logger.info(f"Generated {len(queries)} queries for {self.analyst_type}: {queries}")

            if not queries:
                raise ValueError(f"No queries generated for {company}")

            # Limit to at most 4 queries.
            queries = queries[:4]
            logger.info(f"Final queries for {self.analyst_type}: {queries}")
            
            return queries
            
        except Exception as e:
            logger.error(f"Error generating queries for {company}: {e}")
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="error",
                    message=f"Failed to generate research queries: {str(e)}",
                    error=f"Query generation failed: {str(e)}"
                )
            return []

    def _format_query_prompt(self, prompt, company, hq, year):
        return f"""{prompt}

        Important Guidelines:
        - Focus ONLY on {company}-specific information
        - Make queries very brief and to the point
        - Provide exactly 4 search queries (one per line), with no hyphens or dashes
        - DO NOT make assumptions about the industry - use only the provided industry information"""

    def _fallback_queries(self, company, year):
        return [
            f"{company} overview {year}",
            f"{company} recent news {year}",
            f"{company} financial reports {year}",
            f"{company} industry analysis {year}"
        ]

    async def search_single_query(self, query: str, websocket_manager=None, job_id=None) -> Dict[str, Any]:
        """Execute a single search query with proper error handling."""
        try:
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="query_searching",
                    message=f"Searching: {query}",
                    result={
                        "step": "Searching",
                        "query": query
                    }
                )

            if self.use_local_data:
                # 本地数据模式
                results = await self.local_data_manager.get_search_results(query)
            else:
                # Tavily API 模式
                # search_params = {
                #     "search_depth": "basic",
                #     "include_raw_content": False,
                #     "max_results": 5
                # }
                # if self.analyst_type == "news_analyst":
                #     search_params["topic"] = "news"
                # elif self.analyst_type == "financial_analyst":
                #     search_params["topic"] = "finance"
                # results = await self.tavily_client.search(query, **search_params)
                pass
            
            docs = {}
            for result in results.get("results", []):
                if not result.get("content") or not result.get("url"):
                    continue
                    
                url = result.get("url")
                title = result.get("title", "")
                
                # Clean up and validate the title using the references module
                if title:
                    title = clean_title(title)
                    # If title is the same as URL or empty, set to empty to trigger extraction later
                    if title.lower() == url.lower() or not title.strip():
                        title = ""
                
                logger.info(f"{'Local' if self.use_local_data else 'Tavily'} search result for '{query}': URL={url}, Title='{title}'")
                
                docs[url] = {
                    "title": title,
                    "content": result.get("content", ""),
                    "query": query,
                    "url": url,
                    "source": "local_data" if self.use_local_data else "web_search",
                    "score": result.get("score", 0.0)
                }

            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="query_searched",
                    message=f"Found {len(docs)} results for: {query}",
                    result={
                        "step": "Searching",
                        "query": query,
                        "results_count": len(docs)
                    }
                )

            return docs
            
        except Exception as e:
            logger.error(f"Error searching query '{query}': {e}")
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="query_error",
                    message=f"Search failed for: {query}",
                    result={
                        "step": "Searching",
                        "query": query,
                        "error": str(e)
                    }
                )
            return {}

    async def search_documents(self, state: ResearchState, queries: List[str]) -> Dict[str, Any]:
        websocket_manager = state.get('websocket_manager')
        job_id = state.get('job_id')
        company = state.get('company', 'Unknown Company')

        if not queries:
            logger.error("No valid queries to search")
            return {}

        if websocket_manager and job_id:
            await websocket_manager.send_status_update(
                job_id=job_id,
                status="queries_generated",
                message=f"Generated {len(queries)} queries for {self.analyst_type}",
                result={
                    "step": "Searching",
                    "analyst": self.analyst_type,
                    "queries": queries,
                    "total_queries": len(queries)
                }
            )

        merged_docs = {}
        if self.use_local_data:
            # 本地数据模式
            for query in queries:
                results = await self.local_data_manager.get_search_results(query, company=company)
                if results and results.get("results"):
                    for result in results["results"]:
                        url = result.get("url")
                        if url:
                            merged_docs[url] = {
                                "title": result.get("title", ""),
                                "content": result.get("content", ""),
                                "query": query,
                                "url": url,
                                "source": "local_data",  # 强制设置为 local_data
                                "score": result.get("score", 0.0)
                            }
        else:
            # API模式，自动保存本地数据
            search_params = {
                "search_depth": "basic",
                "include_raw_content": False,
                "max_results": 5
            }
            if self.analyst_type == "news_analyst":
                search_params["topic"] = "news"
            elif self.analyst_type == "financial_analyst":
                search_params["topic"] = "finance"
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="search_started",
                    message=f"Using Tavily to search for {len(queries)} queries",
                    result={
                        "step": "Searching",
                        "total_queries": len(queries)
                    }
                )
            search_tasks = [
                self.tavily_client.search(query, **search_params)
                for query in queries
            ]
            try:
                results = await asyncio.gather(*search_tasks)
                for query, result in zip(queries, results):
                    docs = {}
                    for item in result.get("results", []):
                        if not item.get("content") or not item.get("url"):
                            continue
                        url = item.get("url")
                        title = item.get("title", "")
                        if title:
                            title = clean_title(title)
                            if title.lower() == url.lower() or not title.strip():
                                title = ""
                        doc = {
                            "title": title,
                            "content": item.get("content", ""),
                            "query": query,
                            "url": url,
                            "source": "web_search",
                            "score": item.get("score", 0.0)
                        }
                        docs[url] = doc
                        merged_docs[url] = doc
                    # API模式下自动保存本地数据
                    self.local_data_manager.save_search_results(company, query, docs)
                    if websocket_manager and job_id:
                        await websocket_manager.send_status_update(
                            job_id=job_id,
                            status="query_searched",
                            message=f"Found {len(docs)} results for: {query}",
                            result={
                                "step": "Searching",
                                "query": query,
                                "results_count": len(docs)
                            }
                        )
            except Exception as e:
                logger.error(f"Error during parallel search execution: {e}")
                if websocket_manager and job_id:
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="query_error",
                        message=f"Search failed: {str(e)}",
                        result={
                            "step": "Searching",
                            "error": str(e)
                        }
                    )
                return {}
        return merged_docs

    async def process_text_with_references(self, text: str, state: ResearchState) -> str:
        """处理文本，添加引用标记
        
        Args:
            text: 要处理的文本
            state: 研究状态，包含数据源信息
            
        Returns:
            str: 处理后的文本，包含引用标记
        """
        if not text:
            return text
            
        # 重置文本链接器状态
        self.text_linker.reset()
        
        # 从状态中获取数据源
        data_sources = {
            'company_data': state.get('company_data', {}),
            'financial_data': state.get('financial_data', {}),
            'news_data': state.get('news_data', {}),
            'industry_data': state.get('industry_data', {})
        }
        
        # 添加所有数据源到文本链接器
        for category, sources in data_sources.items():
            for url, doc in sources.items():
                if content := doc.get('content'):
                    # 获取标题和分数
                    title = doc.get('title', '')
                    score = doc.get('score', 0.0)
                    # 添加数据源，包含标题信息
                    self.text_linker.add_data_source(content, url, title, score)
        
        try:
            # 处理文本，添加引用标记
            processed_text = await self.text_linker.process_text(text, state)
            
            # 添加引用部分
            references = self.text_linker.get_references_section()
            if references:
                # 使用HTML格式包装引用部分，控制字体大小
                processed_text += f'\n<div style="font-size: 0.9em;">{references}</div>'
                
            return processed_text
        except Exception as e:
            logger.error(f"Error processing text with references: {e}")
            return text

    async def analyze(self, state: ResearchState) -> Dict[str, Any]:
        """分析数据并生成报告"""
        # 获取分析结果
        analysis_result = await self._perform_analysis(state)
        
        # 处理文本，添加引用链接
        if 'message' in analysis_result:
            if isinstance(analysis_result['message'], list):
                # 如果消息是列表，处理每个消息
                analysis_result['message'] = [
                    await self.process_text_with_references(msg, state)
                    if isinstance(msg, str) else msg
                    for msg in analysis_result['message']
                ]
            elif isinstance(analysis_result['message'], str):
                # 如果消息是字符串，直接处理
                analysis_result['message'] = await self.process_text_with_references(
                    analysis_result['message'], state
                )
        
        return analysis_result

    async def _perform_analysis(self, state: ResearchState) -> Dict[str, Any]:
        """执行具体的分析（由子类实现）"""
        raise NotImplementedError("Subclasses must implement _perform_analysis")
