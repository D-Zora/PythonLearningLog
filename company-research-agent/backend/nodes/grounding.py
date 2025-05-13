from langchain_core.messages import AIMessage
import os
import logging
from ..classes import InputState, ResearchState
from tavily import AsyncTavilyClient
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class GroundingNode:
    """Gathers initial grounding data about the company."""
    
    def __init__(self) -> None:
        # Tavily API 配置
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY environment variable is not set")
        self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
        
        # OpenAI API 配置
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.openai_client = AsyncOpenAI(api_key=openai_key, base_url="https://openrouter.ai/api/v1")

    async def initial_search(self, state: InputState) -> ResearchState:
        # Add debug logging at the start to check websocket manager
        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message="Starting initial company research",
                    result={"step": "Initial Research"}
                )

        company = state.get('company', 'Unknown Company')
        msg = f"🎯 Initiating research for {company}...\n\n"
        site_scrape = {}
        error_str = None

        # Only attempt extraction if we have a URL
        if url := state.get('company_url'):
            msg += f"\n🌐 Analyzing company website: {url}"
            logger.info(f"Starting website analysis for {url}")
            
            # Send initial briefing status
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Analyzing company website",
                        result={"step": "Initial Site Scrape"}
                    )

            try:
                # 使用 Tavily API 进行网站分析
                logger.info("Initiating Tavily extraction")
                site_extraction = await self.tavily_client.extract(url, extract_depth="advanced")
                
                raw_contents = []
                for item in site_extraction.get("results", []):
                    if content := item.get("raw_content"):
                        raw_contents.append(content)
                
                if raw_contents:
                    site_scrape = "\n".join(raw_contents)
                    msg += "\n✓ Successfully extracted website content"
                else:
                    msg += "\n⚠️ No content found in website extraction"
                    
            except Exception as e:
                error_str = str(e)
                msg += f"\n⚠️ Error extracting website content: {error_str}"
                logger.error(f"Error during website extraction: {e}")

        # Initialize ResearchState with input information
        research_state = {
            # Copy input fields
            "company": state.get('company'),
            "company_url": state.get('company_url'),
            "hq_location": state.get('hq_location'),
            "industry": state.get('industry'),
            # Initialize research fields
            "messages": [AIMessage(content=msg)],
            "site_scrape": site_scrape,
            # Pass through websocket info
            "websocket_manager": state.get('websocket_manager'),
            "job_id": state.get('job_id')
        }

        # If there was an error in the initial extraction, store it in the state
        if "⚠️ Error extracting website content:" in msg:
            research_state["error"] = error_str

        return research_state

    async def run(self, state: InputState) -> ResearchState:
        return await self.initial_search(state)
