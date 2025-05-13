from langchain_core.messages import AIMessage
from typing import Dict, Any, List
from openai import AsyncOpenAI
import os
import logging
import re

logger = logging.getLogger(__name__)

from ..classes import ResearchState
from ..utils.references import format_references_section
from ..utils.text_reference_linker import TextReferenceLinker
from ..utils.local_data import LocalDataManager

class Editor:
    """Compiles individual section briefings into a cohesive final report."""
    
    def __init__(self) -> None:
        self.openai_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Configure OpenAI
        self.openai_client = AsyncOpenAI(api_key=self.openai_key, base_url="https://openrouter.ai/api/v1")
        
        # Initialize context dictionary for use across methods
        self.context = {
            "company": "Unknown Company",
            "industry": "Unknown",
            "hq_location": "Unknown"
        }
        
        # 初始化数据管理器和文本引用链接器
        self.local_data_manager = LocalDataManager()
        self.text_linker = TextReferenceLinker(data_dir=self.local_data_manager.data_dir)

    def _build_compilation_prompt(self, briefings: Dict[str, str], company: str) -> str:
        """构建用于编译报告的提示词。"""
        # 获取各个部分的简报内容
        company_briefing = briefings.get('company', 'No company briefing available')
        industry_briefing = briefings.get('industry', 'No industry briefing available')
        financial_briefing = briefings.get('financial', 'No financial briefing available')
        news_briefing = briefings.get('news', 'No news briefing available')

        # 构建提示词
        prompt = f"""You are an expert report editor tasked with compiling a comprehensive research report for {company}.

Please compile the following research briefings into a cohesive report:

COMPANY BRIEFING:
{company_briefing}

INDUSTRY BRIEFING:
{industry_briefing}

FINANCIAL BRIEFING:
{financial_briefing}

NEWS BRIEFING:
{news_briefing}

Please follow these guidelines:
1. Create a well-structured report with clear sections and subsections
2. Maintain all factual information and data points
3. Ensure smooth transitions between sections
4. Remove any redundant information
5. Keep the tone professional and objective
6. Include all relevant metrics and statistics
7. Preserve any source citations or references
8. Format the report in markdown

The report should follow this structure:
# {company} Research Report

## Company Overview
[Company information, history, business model, etc.]

## Industry Overview
[Industry analysis, market trends, competitive landscape]

## Financial Overview
[Financial performance, key metrics, analysis]

## News
[Recent developments, significant events]

Please compile the report now, ensuring all information is accurate and well-organized."""

        return prompt

    async def compile_briefings(self, state: ResearchState) -> ResearchState:
        """Compile individual briefing categories from state into a final report."""
        company = state.get('company', 'Unknown Company')
        
        # Update context with values from state
        self.context = {
            "company": company,
            "industry": state.get('industry', 'Unknown'),
            "hq_location": state.get('hq_location', 'Unknown')
        }
        
        # Send initial compilation status
        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message=f"Starting report compilation for {company}",
                    result={
                        "step": "Editor",
                        "substep": "initialization"
                    }
                )

        context = {
            "company": company,
            "industry": state.get('industry', 'Unknown'),
            "hq_location": state.get('hq_location', 'Unknown')
        }
        
        msg = [f"📑 Compiling final report for {company}..."]
        
        # Pull individual briefings from dedicated state keys
        briefing_keys = {
            'company': 'company_briefing',
            'industry': 'industry_briefing',
            'financial': 'financial_briefing',
            'news': 'news_briefing'
        }

        # Send briefing collection status
        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message="Collecting section briefings",
                    result={
                        "step": "Editor",
                        "substep": "collecting_briefings"
                    }
                )

        individual_briefings = {}
        for category, key in briefing_keys.items():
            if content := state.get(key):
                individual_briefings[category] = content
                msg.append(f"Found {category} briefing ({len(content)} characters)")
            else:
                msg.append(f"No {category} briefing available")
                logger.error(f"Missing state key: {key}")
        
        if not individual_briefings:
            msg.append("\n⚠️ No briefing sections available to compile")
            logger.error("No briefings found in state")
        else:
            try:
                compiled_report = await self.edit_report(state, individual_briefings, context)
                if not compiled_report or not compiled_report.strip():
                    logger.error("Compiled report is empty!")
                else:
                    logger.info(f"Successfully compiled report with {len(compiled_report)} characters")
            except Exception as e:
                logger.error(f"Error during report compilation: {e}")
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        return state
    
    async def edit_report(self, state: ResearchState, briefings: Dict[str, str], context: Dict[str, Any]) -> str:
        """Compile section briefings into a final report and update the state."""
        try:
            company = self.context["company"]
            
            # Step 1: Initial Compilation
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Compiling initial research report",
                        result={
                            "step": "Editor",
                            "substep": "compilation"
                        }
                    )

            edited_report = await self.compile_content(state, briefings, company)
            if not edited_report:
                logger.error("Initial compilation failed")
                return ""

            # Step 2: Deduplication and Cleanup
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Cleaning up and organizing report",
                        result={
                            "step": "Editor",
                            "substep": "cleanup"
                        }
                    )

            # Step 3: Formatting Final Report
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Formatting final report",
                        result={
                            "step": "Editor",
                            "substep": "format"
                        }
                    )
            final_report = await self.content_sweep(state, edited_report, company)
            
            final_report = final_report or ""
            
            logger.info(f"Final report compiled with {len(final_report)} characters")
            if not final_report.strip():
                logger.error("Final report is empty!")
                return ""
            
            logger.info("Final report preview:")
            logger.info(final_report[:500])
            
            # Update state with the final report in two locations
            state['report'] = final_report
            state['status'] = "editor_complete"
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = final_report
            logger.info(f"Report length in state: {len(state.get('report', ''))}")
            
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="editor_complete",
                        message="Research report completed",
                        result={
                            "step": "Editor",
                            "report": final_report,
                            "company": company,
                            "is_final": True,
                            "status": "completed"
                        }
                    )
            
            return final_report
        except Exception as e:
            logger.error(f"Error in edit_report: {e}")
            return ""
    
    async def compile_content(self, state: ResearchState, briefings: Dict[str, str], company: str) -> str:
        """Initial compilation of research sections."""
        try:
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
            
            # 构建提示词
            prompt = self._build_compilation_prompt(briefings, company)
            
            # 获取初始报告
            response = await self.openai_client.chat.completions.create(
                model="openai/gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert report editor that compiles research briefings into comprehensive company reports."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                stream=False
            )
            initial_report = response.choices[0].message.content.strip()
            
            # 处理每个段落，添加引用链接
            paragraphs = initial_report.split('\n\n')
            processed_paragraphs = []
            
            logger.info(f"Processing {len(paragraphs)} paragraphs for reference linking")
            
            for i, paragraph in enumerate(paragraphs):
                # 跳过标题行
                if paragraph.startswith('#') or paragraph.startswith('##') or paragraph.startswith('###'):
                    processed_paragraphs.append(paragraph)
                    continue
                
                # 首先使用 find_matching_content 找到匹配的内容
                matches = self.text_linker.find_matching_content(paragraph)
                if matches:
                    logger.info(f"Found {len(matches)} matches for paragraph {i+1}")
                    # 记录匹配结果，但不直接修改文本
                    for match in matches:
                        logger.debug(f"Match found: {match['url']} (score: {match['score']})")
                
                # 使用 TextReferenceLinker 处理段落内容
                context = {
                    "company": company,
                    "industry": state.get('industry', 'Unknown'),
                    "analyst_type": "editor"
                }
                processed_para = await self.text_linker.process_text(paragraph, context)
                if processed_para != paragraph:
                    logger.info(f"Added references to paragraph {i+1}")
                processed_paragraphs.append(processed_para)
            
            # 重新组合处理后的段落
            final_report = '\n\n'.join(processed_paragraphs)
            
            # 添加引用部分
            references = self.text_linker.get_references_section()
            if references:
                final_report += f'\n<div style="font-size: 0.9em;">{references}</div>'
            
            return final_report
            
        except Exception as e:
            logger.error(f"Error in compilation: {e}")
            return ""
        
    async def content_sweep(self, state: ResearchState, content: str, company: str) -> str:
        """Sweep the content for any redundant information."""
        # Use values from centralized context
        company = self.context["company"]
        industry = self.context["industry"]
        hq_location = self.context["hq_location"]
        
        prompt = f"""You are an expert briefing editor. You are given a report on {company}.

Current report:
{content}

1. Remove redundant or repetitive information
2. Remove information that is not relevant to {company}, the {industry} company headquartered in {hq_location}.
3. Remove sections lacking substantial content
4. Remove any meta-commentary (e.g. "Here is the news...")
5. DO NOT modify any reference links in the format [🔗](url) - they are clickable citations

Strictly enforce this EXACT document structure:

# {company} Research Report

## Company Overview
[Company content with ### subsections]

## Industry Overview
[Industry content with ### subsections]

## Financial Overview
[Financial content with ### subsections]

## News
[News content with ### subsections]

Critical rules:
1. The document MUST start with "# {company} Research Report"
2. The document MUST ONLY use these exact ## headers in this order:
   - ## Company Overview
   - ## Industry Overview
   - ## Financial Overview
   - ## News
3. NO OTHER ## HEADERS ARE ALLOWED
4. Use ### for subsections in Company/Industry/Financial sections
5. News section should only use bullet points (*), never headers
6. Never use code blocks (```)
7. Never use more than one blank line between sections
8. Format all bullet points with *
9. Add one blank line before and after each section/list
10. DO NOT modify any reference links in the format [🔗](url) - they are clickable citations
11. DO NOT remove or modify any data points that have source links

Return the polished report in flawless markdown format. No explanation."""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="openai/gpt-4.1-mini", 
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert markdown formatter that ensures consistent document structure. Never modify reference links in the format [🔗](url)."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                stream=True
            )
            
            accumulated_text = ""
            buffer = ""
            
            async for chunk in response:
                if chunk.choices[0].finish_reason == "stop":
                    websocket_manager = state.get('websocket_manager')
                    if websocket_manager and buffer:
                        job_id = state.get('job_id')
                        if job_id:
                            await websocket_manager.send_status_update(
                                job_id=job_id,
                                status="report_chunk",
                                message="Formatting final report",
                                result={
                                    "chunk": buffer,
                                    "step": "Editor"
                                }
                            )
                    break
                    
                chunk_text = chunk.choices[0].delta.content
                if chunk_text:
                    accumulated_text += chunk_text
                    buffer += chunk_text
                    
                    if any(char in buffer for char in ['.', '!', '?', '\n']) and len(buffer) > 10:
                        if websocket_manager := state.get('websocket_manager'):
                            if job_id := state.get('job_id'):
                                await websocket_manager.send_status_update(
                                    job_id=job_id,
                                    status="report_chunk",
                                    message="Formatting final report",
                                    result={
                                        "chunk": buffer,
                                        "step": "Editor"
                                    }
                                )
                        buffer = ""
            
            # 确保引用链接格式正确
            final_text = accumulated_text.strip()
            
            # 再次使用 TextReferenceLinker 处理文本，确保所有数据点都有来源链接
            context = {
                "company": company,
                "industry": industry,
                "analyst_type": "editor"
            }
            final_text = await self.text_linker.process_text(final_text, context)
            
            return final_text
        except Exception as e:
            logger.error(f"Error in formatting: {e}")
            return (content or "").strip()

    async def run(self, state: ResearchState) -> ResearchState:
        state = await self.compile_briefings(state)
        # Ensure the Editor node's output is stored both top-level and under "editor"
        if 'report' in state:
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = state['report']
        return state
