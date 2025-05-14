from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from pathlib import Path
from dotenv import load_dotenv
import uuid
import logging
import asyncio
import uvicorn

# 环境变量
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# 导入生成报告的逻辑
from backend.graph import Graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="公司研究报告API")

class CompanyResearchRequest(BaseModel):
    company: str
    company_url: Optional[str] = None

@app.post("/api/research")
async def stream_research_report(request: Request, body: CompanyResearchRequest):

    task_id = str(uuid.uuid4())

    async def event_stream() -> AsyncGenerator[bytes, None]:
        try:
            graph = Graph(
                company=body.company,
                url=body.company_url,
                websocket_manager=None,
                job_id=task_id
            )

            state = {}
            seen_lines = set()

            # 运行研究任务
            async for s in graph.run(thread={}):
                state.update(s)

                report = state.get("report")
                if report:
                    for line in report.strip().splitlines():
                        line = line.strip()
                        if not line or line in seen_lines:
                            continue
                        seen_lines.add(line)
                        yield f"data: {line}\n\n".encode("utf-8")
                        await asyncio.sleep(0.05)  # 控制节奏

            yield f"event: done\ndata: 研究报告生成完成\n\n".encode("utf-8")

        except Exception as e:
            logger.exception("研究失败")
            yield f"event: error\ndata: {str(e)}\n\n".encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
