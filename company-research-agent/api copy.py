from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import asyncio
import uuid
from datetime import datetime
import logging
from pathlib import Path
import os
from dotenv import load_dotenv
from sse_starlette.sse import EventSourceResponse
from collections.abc import AsyncGenerator

# 加载环境变量
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# 导入必要的服务
from backend.graph import Graph
from backend.services.websocket_manager import WebSocketManager
from backend.services.mongodb import MongoDBService
from backend.services.pdf_service import PDFService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="公司研究API",
    description="一个统一的公司研究API接口，整合了研究、报告生成和PDF导出功能",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化服务
manager = WebSocketManager()
pdf_service = PDFService({"pdf_output_dir": "pdfs"})
mongodb = MongoDBService(os.getenv("MONGODB_URI")) if os.getenv("MONGODB_URI") else None

# 存储任务状态
tasks: Dict[str, Dict[str, Any]] = {}

# 请求模型
class CompanyResearchRequest(BaseModel):
    """公司研究请求模型"""
    company: str
    company_url: Optional[str] = None
    industry: Optional[str] = None
    hq_location: Optional[str] = None
    use_local_data: bool = False
    generate_pdf: bool = False  # 是否自动生成PDF

class ResearchResponse(BaseModel):
    """研究响应模型"""
    task_id: str
    status: str
    message: str
    websocket_url: Optional[str] = None
    report_url: Optional[str] = None
    pdf_url: Optional[str] = None
    error: Optional[str] = None

async def process_research_task(task_id: str, request: CompanyResearchRequest):
    """处理研究任务的后台函数"""
    try:
        tasks[task_id] = {
            "status": "processing",
            "start_time": datetime.now().isoformat(),
            "company": request.company,
            "error": None,
            "report": None,
            "pdf_url": None
        }

        # 创建研究图实例
        graph = Graph(
            company=request.company,
            url=request.company_url,
            industry=request.industry,
            hq_location=request.hq_location,
            websocket_manager=manager,
            job_id=task_id,
            use_local_data=request.use_local_data
        )

        # 执行研究
        state = {}
        async for s in graph.run(thread={}):
            state.update(s)

        # 获取报告内容
        report_content = state.get('report') or (state.get('editor') or {}).get('report')
        
        if not report_content:
            raise Exception("未能生成研究报告")

        # 更新任务状态
        tasks[task_id].update({
            "status": "completed",
            "report": report_content,
            "report_url": f"/api/report/{task_id}"
        })

        # 如果请求生成PDF
        if request.generate_pdf:
            pdf_filename = f"{request.company}_{task_id}.pdf"
            pdf_path = await pdf_service.generate_pdf(report_content, pdf_filename)
            tasks[task_id]["pdf_url"] = f"/api/pdf/{pdf_filename}"

        # 存储到MongoDB（如果配置了）
        if mongodb:
            mongodb.store_report(
                task_id=task_id,
                report_data={
                    "report": report_content,
                    "company": request.company,
                    "metadata": {
                        "industry": request.industry,
                        "location": request.hq_location,
                        "url": request.company_url
                    }
                }
            )

    except Exception as e:
        logger.error(f"研究任务失败: {str(e)}", exc_info=True)
        tasks[task_id].update({
            "status": "failed",
            "error": str(e)
        })
        if mongodb:
            mongodb.update_job(task_id=task_id, status="failed", error=str(e))

@app.post("/api/research", response_model=ResearchResponse)
async def start_research(request: CompanyResearchRequest, background_tasks: BackgroundTasks):
    """启动公司研究任务"""
    try:
        task_id = str(uuid.uuid4())
        
        # 启动后台任务
        background_tasks.add_task(process_research_task, task_id, request)
        
        return ResearchResponse(
            task_id=task_id,
            status="accepted",
            message="研究任务已启动",
            websocket_url=f"/api/ws/{task_id}"
        )
    except Exception as e:
        logger.error(f"启动研究任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status/{task_id}", response_model=ResearchResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    return ResearchResponse(
        task_id=task_id,
        status=task["status"],
        message="任务状态查询成功",
        report_url=task.get("report_url"),
        pdf_url=task.get("pdf_url"),
        error=task.get("error")
    )

@app.get("/api/report/{task_id}")
async def get_report(task_id: str):
    """获取研究报告"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="报告尚未生成")
    
    return {"report": task["report"]}

@app.get("/api/pdf/{filename}")
async def get_pdf(filename: str):
    """获取PDF文件"""
    pdf_path = os.path.join("pdfs", filename)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF文件不存在")
    return FileResponse(pdf_path, media_type='application/pdf', filename=filename)

@app.websocket("/api/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket连接端点，用于实时获取任务状态"""
    try:
        await websocket.accept()
        await manager.connect(websocket, task_id)
        
        if task_id in tasks:
            task = tasks[task_id]
            await manager.send_status_update(
                task_id,
                status=task["status"],
                message="已连接到状态流",
                error=task.get("error"),
                result={
                    "report_url": task.get("report_url"),
                    "pdf_url": task.get("pdf_url")
                }
            )
        
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                manager.disconnect(websocket, task_id)
                break
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}", exc_info=True)
        await websocket.close()

@app.get("/api/sse/{task_id}")
async def stream_updates(task_id: str, request: Request):
    """以流式方式SSE返回已生成的研究报告内容"""
    # 校验任务是否存在
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]

    # 报告尚未生成
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="报告尚未生成")
    
    report_content = task["report"]

    if not report_content:
        raise HTTPException(status_code=400, detail="报告内容为空")
    
    async def report_generator() -> AsyncGenerator[str, None]:
        """生成报告内容的异步生成器"""
        try:
            for i,line in enumerate(report_content.splitlines()):
                if await request.is_disconnected():
                    break
                event = f"id:{i}\nevent:message\ndata:{line}\n\n"
                yield event
                await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"SSE发送错误: {str(e)}")

    return EventSourceResponse(report_generator(), media_type="text/event-stream")
@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 