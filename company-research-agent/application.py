# 项目入口文件
import os
from pathlib import Path
from dotenv import load_dotenv

# 启动时时加载当前目录下的.env文件，把里面定义的变量注入到os.environ中
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from backend.graph import Graph # 图形流程或任务图，执行实际的研究任务
from backend.services.websocket_manager import WebSocketManager # WebSocket管理器，管理连接并发送更新
import logging
import uvicorn
from datetime import datetime
import asyncio
import uuid
from collections import defaultdict
from backend.services.mongodb import MongoDBService # MongoDB服务，用于存储和检索研究结果
from backend.services.pdf_service import PDFService # PDF服务，用于生成PDF报告

# 配置日志记录器
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 配置控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# 配置文件处理器
file_handler = logging.FileHandler(log_dir / "app.log")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# 添加处理器到日志记录器
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# 创建FastAPI应用实例
app = FastAPI(title="Tavily Company Research API")

# 添加CORS中间件，允许跨域请求，使前端可以访问后端
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 创建WebSocket管理器实例
manager = WebSocketManager()

# 创建PDF服务实例
pdf_service = PDFService({"pdf_output_dir": "pdfs"})

# 创建一个字典来存储每个研究任务的状态
job_status = defaultdict(lambda: {
    "status": "pending", # 任务状态，pending表示等待，processing表示处理中，completed表示完成，failed表示失败
    "result": None, # 任务结果
    "error": None, # 任务错误信息
    "debug_info": [], # 调试信息
    "company": None, # 公司名称
    "report": None, # 报告内容
    "last_update": datetime.now().isoformat() # 最后更新时间    
})

# 创建MongoDB服务实例（如果配置了MongoDB URI）
mongodb = None
if mongodb_uri := os.getenv("MONGODB_URI"):
    try:
        mongodb = MongoDBService(mongodb_uri)
        logger.info("MongoDB service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB service: {e}")

# 定义研究请求模型
class ResearchRequest(BaseModel):
    company: str
    company_url: str | None = None
    industry: str | None = None
    hq_location: str | None = None
    use_local_data: bool = False  # 默认使用本地数据模式

# 定义PDF生成请求模型，定义了但好像未调用
class PDFGenerationRequest(BaseModel):
    report_content: str # 报告内容
    company_name: str | None = None # 公司名称

# 定义PDF生成请求模型
class GeneratePDFRequest(BaseModel):
    report_content: str # 报告内容
    company_name: str | None = None # 公司名称

# 定义预检请求处理函数
@app.options("/research")
async def preflight():
    response = JSONResponse(content=None, status_code=200)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

# 定义研究请求处理函数
@app.post("/research")
async def research(data: ResearchRequest):
    try:
        logger.info(f"Received research request for {data.company}")
        job_id = str(uuid.uuid4())
        asyncio.create_task(process_research(job_id, data))

        response = JSONResponse(content={
            "status": "accepted",
            "job_id": job_id,
            "message": "Research started. Connect to WebSocket for updates.",
            "websocket_url": f"/research/ws/{job_id}"
        })
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    except Exception as e:
        logger.error(f"Error initiating research: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# 定义研究处理函数
async def process_research(job_id: str, data: ResearchRequest):
    try:
        if mongodb:
            mongodb.create_job(job_id, data.dict())
        await asyncio.sleep(1)  # 等待1秒，允许WebSocket连接

        # 发送状态更新
        await manager.send_status_update(job_id, status="processing", message="Starting research")

        # 创建图形流程或任务图实例
        graph = Graph(
            company=data.company,
            url=data.company_url,
            industry=data.industry,
            hq_location=data.hq_location,
            websocket_manager=manager,
            job_id=job_id,
            use_local_data=data.use_local_data  # 传递本地数据模式选项
        )

        state = {}
        async for s in graph.run(thread={}):
            state.update(s)
        
        # 从状态中获取报告内容
        report_content = state.get('report') or (state.get('editor') or {}).get('report')
        if report_content:
            logger.info(f"Found report in final state (length: {len(report_content)})")
            job_status[job_id].update({
                "status": "completed",
                "report": report_content,
                "company": data.company,
                "last_update": datetime.now().isoformat()
            })
            if mongodb:
                mongodb.update_job(job_id=job_id, status="completed")
                mongodb.store_report(job_id=job_id, report_data={"report": report_content})
            await manager.send_status_update(
                job_id=job_id,
                status="completed",
                message="Research completed successfully",
                result={
                    "report": report_content,
                    "company": data.company
                }
            )
        else:
            logger.error(f"Research completed without finding report. State keys: {list(state.keys())}")
            logger.error(f"Editor state: {state.get('editor', {})}")
            
            # 如果状态中没有报告，则设置错误信息
            error_message = "No report found"
            if error := state.get('error'):
                error_message = f"Error: {error}"
            
            await manager.send_status_update(
                job_id=job_id,
                status="failed",
                message="Research completed but no report was generated",
                error=error_message
            )

    except Exception as e:
        logger.error(f"Research failed: {str(e)}")
        await manager.send_status_update(
            job_id=job_id,
            status="failed",
            message=f"Research failed: {str(e)}",
            error=str(e)
        )
        if mongodb:
            mongodb.update_job(job_id=job_id, status="failed", error=str(e))

# 定义获取请求处理函数
@app.get("/")
async def ping():
    return {"message": "Alive"}

# 定义获取PDF请求处理函数
@app.get("/research/pdf/{filename}")
async def get_pdf(filename: str):
    pdf_path = os.path.join("pdfs", filename)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type='application/pdf', filename=filename)

# 定义WebSocket请求处理函数
@app.websocket("/research/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    try:
        await websocket.accept()
        await manager.connect(websocket, job_id)

        if job_id in job_status:
            status = job_status[job_id]
            await manager.send_status_update(
                job_id,
                status=status["status"],
                message="Connected to status stream",
                error=status["error"],
                result=status["result"]
            )

        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                manager.disconnect(websocket, job_id)
                break

    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {str(e)}", exc_info=True)
        manager.disconnect(websocket, job_id)

# 定义获取请求处理函数
@app.get("/research/{job_id}")
async def get_research(job_id: str):
    if not mongodb:
        raise HTTPException(status_code=501, detail="Database persistence not configured")
    job = mongodb.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return job

# 定义获取请求处理函数
@app.get("/research/{job_id}/report")
async def get_research_report(job_id: str):
    if not mongodb:
        if job_id in job_status:
            result = job_status[job_id]
            if report := result.get("report"):
                return {"report": report}
        raise HTTPException(status_code=404, detail="Report not found")
    
    report = mongodb.get_report(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Research report not found")
    return report

# 定义生成PDF请求处理函数
@app.post("/research/{job_id}/generate-pdf")
async def generate_pdf(job_id: str):
    return pdf_service.generate_pdf_from_job(job_id, job_status, mongodb)

# 定义生成PDF请求处理函数
@app.post("/generate-pdf")
async def generate_pdf(data: GeneratePDFRequest):
    """Generate a PDF from markdown content and stream it to the client."""
    try:
        success, result = pdf_service.generate_pdf_stream(data.report_content, data.company_name)
        if success:
            pdf_buffer, filename = result
            return StreamingResponse(
                pdf_buffer,
                media_type='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        else:
            raise HTTPException(status_code=500, detail=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)