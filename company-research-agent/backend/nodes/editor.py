from langchain_core.messages import AIMessage
from typing import Dict, Any, List
from openai import AsyncOpenAI
import os
import logging
import re
import json

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
7. Preserve any source citations or references in the format <sup>[n]</sup> where n is the reference number
8. Format the report in markdown
9. Do not modify or remove any existing reference marks in the format <sup>[n]</sup>

# Report Format

description:
Format Rules:
1. Concise content with clear structure
2. Cite all facts and data
3. Use [^n] for citations
4. Valid URLs only (http://, https://, www.)
5. Include source title and domain

Example:
Tesla Q4 2023: $25.17B revenue[^1], +3% YoY[^2], 484,507 deliveries[^3].

References:
[^1]: [Tesla Q4 2023 Results](https://ir.tesla.com/press-release/tesla-announces-fourth-quarter-2023-financial-results) - ir.tesla.com
[^2]: [Tesla Q4 2023 Report](https://www.sec.gov/Archives/edgar/data/1318605/000095017024000409/tsla-10k_20231231.htm) - sec.gov
[^3]: [Tesla Q4 2023 Deliveries](https://www.tesla.com/blog/tesla-q4-2023-vehicle-production-deliveries) - tesla.com

Note: Invalid URLs will be filtered.

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
        logger.info(f"Starting report compilation for company: {company}")
        logger.info(f"Current state keys: {list(state.keys())}")
        
        # Update context with values from state
        self.context = {
            "company": company,
            "industry": state.get('industry', 'Unknown'),
            "hq_location": state.get('hq_location', 'Unknown')
        }
        logger.info(f"Updated context: {self.context}")
        
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
                # 检查简报内容是否有效
                if isinstance(content, str) and content.strip():
                    individual_briefings[category] = content
                    msg.append(f"Found {category} briefing ({len(content)} characters)")
                    logger.info(f"Valid {category} briefing found: {content[:100]}...")
                else:
                    msg.append(f"Invalid {category} briefing content")
                    logger.error(f"Invalid content for state key: {key}, content type: {type(content)}, content length: {len(str(content)) if content else 0}")
            else:
                msg.append(f"No {category} briefing available")
                logger.error(f"Missing state key: {key}, available keys: {list(state.keys())}")
        
        if not individual_briefings:
            msg.append("\n⚠️ No valid briefing sections available to compile")
            logger.error("No valid briefings found in state")
            state['status'] = "editor_failed"
            state['error'] = "No valid briefings available for compilation"
            return state
        else:
            try:
                compiled_report = await self.edit_report(state, individual_briefings, context)
                if not compiled_report or not compiled_report.strip():
                    logger.error("Compiled report is empty!")
                    state['status'] = "editor_failed"
                    state['error'] = "Failed to compile report from briefings"
                else:
                    logger.info(f"Successfully compiled report with {len(compiled_report)} characters")
                    state['status'] = "editor_complete"
            except Exception as e:
                logger.error(f"Error during report compilation: {e}")
                state['status'] = "editor_failed"
                state['error'] = str(e)
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
            
            # 如果 content_sweep 返回空字符串，使用初始编译的报告
            if not final_report or not final_report.strip():
                logger.warning("Content sweep returned empty report, using initial compilation")
                final_report = edited_report
            
            logger.info(f"Final report compiled with {len(final_report)} characters")
            if not final_report.strip():
                logger.error("Both initial compilation and content sweep failed to generate report")
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
        """编译研究内容，添加引用链接"""
        try:
            # 重置文本链接器状态
            self.text_linker.reset()
            
            # 收集所有数据源
            logger.info(f"Data source counts: { {k: len(v) for k, v in briefings.items()} }")
            
            # 从状态中获取数据源信息
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
                        title = doc.get('title', '')
                        score = doc.get('score', 0.0)
                        self.text_linker.add_data_source(content, url, title, score)
                        logger.info(f"Added source from {category}: url='{url}', title='{title}', score={score}")
            
            # 添加简报内容作为额外数据源
            for category, content in briefings.items():
                if isinstance(content, str) and content.strip():
                    # 为简报内容生成一个唯一的URL
                    url = f"briefing://{category}"
                    self.text_linker.add_data_source(content, url, f"{category} Briefing", 0.5)
                    logger.debug(f"Added briefing source: {category}")
            
            # 构建提示词
            prompt = f"""Please generate a detailed research report based on the following research briefings. Requirements:

1. Use Markdown format for the entire report
2. For any data that needs citation, ONLY use Markdown footnote format with [^n] where n is the footnote number
3. DO NOT use HTML sup tags or any other citation formats
4. Use simple bullet points (*) for lists
5. Keep paragraphs concise and well-structured
6. Maintain a professional and objective tone
7. Ensure data accuracy and traceability
8. Each footnote should be a clickable link to its source
9. Include a References section at the end using the format:
   [^n]: [Title](URL) - Domain
10. IMPORTANT: 
    - Use ONLY [^n] format for citations
    - Never use <sup> tags or other citation formats
    - Keep formatting simple and consistent
    - Use only basic Markdown elements (headings, bullet points, links)
    - Each citation should appear only once in the text

Research briefings:
{json.dumps(briefings, ensure_ascii=False, indent=2)}

Please generate a clean, well-organized research report with proper citations using ONLY Markdown footnotes."""

            # 发送编译请求到 LLM
            logger.info("Sending compilation request to LLM...")
            response = await self.openai_client.chat.completions.create(
                model="openai/gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a professional research report writer. You must use ONLY Markdown footnote format [^n] for citations. Never use HTML sup tags or other citation formats. Each citation should appear only once in the text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            initial_report = response.choices[0].message.content.strip()
            logger.info(f"Received initial report from LLM, length: {len(initial_report)}")
            logger.debug(f"Initial report preview: {initial_report[:200]}")
            
            # 处理每个段落，添加引用链接
            paragraphs = initial_report.split('\n\n')
            processed_paragraphs = []
            
            logger.info(f"Processing {len(paragraphs)} paragraphs for reference linking")
            
            for i, paragraph in enumerate(paragraphs):
                # 跳过标题行
                if paragraph.startswith('#') or paragraph.startswith('##') or paragraph.startswith('###'):
                    processed_paragraphs.append(paragraph)
                    continue
                
                # 移除任何 HTML sup 标签和重复的引用
                paragraph = re.sub(r'<sup>\[.*?\]</sup>', '', paragraph)  # 移除 HTML sup 标签
                paragraph = re.sub(r'\[\^(\d+)\].*?\[\^\1\]', r'[^\1]', paragraph)  # 移除重复的引用
                paragraph = re.sub(r'\[\^(\d+)\].*?<sup>\[\1.*?\]</sup>', r'[^\1]', paragraph)  # 移除引用和 sup 标签的组合
                
                # 使用 TextReferenceLinker 处理段落内容
                processed_para = self.text_linker.process_text(paragraph)
                if processed_para != paragraph:
                    logger.info(f"Added references to paragraph {i+1}")
                    logger.debug(f"Original: {paragraph[:100]}...")
                    logger.debug(f"Processed: {processed_para[:100]}...")
                processed_paragraphs.append(processed_para)
            
            # 重新组合处理后的段落
            final_report = '\n\n'.join(processed_paragraphs)
            
            # 添加引用部分
            references = self.text_linker.get_references_section()
            if references:
                # 移除引用部分中的 HTML 标签
                references = re.sub(r'<.*?>', '', references)
                final_report += f'\n\n## 参考文献\n\n{references}'
                logger.info("Added references section to final report")
            
            return final_report
            
        except Exception as e:
            logger.error(f"Error in compilation: {e}")
            return ""
        
    async def content_sweep(self, state: ResearchState, content: str, company: str) -> str:
        """Sweep the content for any redundant information."""
        try:
            logger.info(f"Starting content sweep for {company}")
            logger.info(f"Input content length: {len(content)}")
            logger.debug(f"Input content preview: {content[:200]}")
            
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
5. DO NOT modify or remove any reference marks in the format <sup>[n]</sup> - they are important citations
6. DO NOT modify or remove any data points that have reference marks

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
10. DO NOT modify or remove any reference marks in the format <sup>[n]</sup>
11. DO NOT remove or modify any data points that have reference marks
12. Keep all reference marks exactly as they appear in the text

Return the polished report in flawless markdown format. No explanation."""
        
            response = await self.openai_client.chat.completions.create(
                model="openai/gpt-4.1",  # 使用与 compile_content 相同的模型
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert markdown formatter that ensures consistent document structure. Never modify reference marks in the format <sup>[n]</sup>."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                stream=False  # 不使用流式输出，确保完整性
            )
            
            final_text = response.choices[0].message.content.strip()
            logger.info(f"Content sweep completed, final text length: {len(final_text)}")
            logger.debug(f"Final text preview: {final_text[:200]}")
            
            # 再次使用 TextReferenceLinker 处理文本，确保所有数据点都有来源链接
            processed_text = self.text_linker.process_text(final_text)
            if processed_text != final_text:
                logger.info("Added additional references during content sweep")
                logger.debug(f"Original: {final_text[:100]}...")
                logger.debug(f"Processed: {processed_text[:100]}...")
            
            return processed_text
        except Exception as e:
            logger.error(f"Error in content sweep: {e}")
            return content  # 如果出错，返回原始内容

    async def run(self, state: ResearchState) -> ResearchState:
        state = await self.compile_briefings(state)
        # Ensure the Editor node's output is stored both top-level and under "editor"
        if 'report' in state:
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = state['report']
        return state
