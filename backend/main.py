"""
DataReportNew - 数据分析报告生成工具
FastAPI 后端服务
"""
import os
import uuid
import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import DataAnalysisAgent


# 项目根目录
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


app = FastAPI(
    title="DataReportNew API",
    description="大模型驱动的数据分析报告生成工具",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    """分析请求"""
    goal: str  # 分析目标
    llm_config: dict  # LLM 配置 {base_url, api_key, model_name}
    file_id: str | None = None  # 可选，已上传的文件ID


class StreamEvent:
    """流式事件类型定义"""
    THINK = "think"          # 推理内容
    DECISION = "decision"    # 工具决策
    CODE = "code"           # 代码内容
    OUTPUT = "output"       # 执行输出
    ANSWER = "answer"       # 面向用户的回答
    PLAN = "plan"           # 分析计划
    STEP_START = "step_start"  # 步骤开始
    STEP_END = "step_end"    # 步骤结束
    COMPLETE = "complete"   # 完成
    ERROR = "error"         # 错误


async def generate_analysis_stream(
    agent: DataAnalysisAgent,
    user_goal: str,
    data_info: dict | None = None
) -> AsyncGenerator[str, None]:
    """
    生成分析过程的流式响应
    使用 SSE (Server-Sent Events) 协议
    """
    import traceback
    step_count = 0

    try:
        async for event in agent.run(user_goal, data_info):
            event_type = event.get("type", "")

            if event_type == "step_start":
                step_count += 1
                yield f"event: step\ndata: {json.dumps({'step': step_count}, ensure_ascii=False)}\n\n"
                continue

            # 构建 SSE 格式的数据
            if "action" in event:
                # Agent 执行步骤结果
                data = {
                    "action": event.get("action"),
                    "analysis": event.get("analysis", ""),
                    "step_summary": event.get("step_summary", ""),
                    "code": event.get("code"),
                    "code_result": event.get("code_result"),
                    "plan": event.get("plan"),
                    "final_answer": event.get("final_answer")
                }
            else:
                # 元数据事件
                data = event

            yield f"event: data\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield f"event: done\ndata: {json.dumps({'message': '分析完成'})}\n\n"

    except Exception as e:
        # 异常时 yield error event 并干净结束 SSE 流 (避免 httpx RemoteProtocolError)
        err_data = {"error": str(e), "type": type(e).__name__}
        yield f"event: error\ndata: {json.dumps(err_data, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'message': '分析异常结束'})}\n\n"


@app.get("/")
async def root():
    """API 根路径"""
    return {"message": "DataReportNew API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传 Excel 数据文件
    返回文件ID和基本信息
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    # 检查文件类型
    allowed_extensions = {".xlsx", ".xls", ".csv"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，仅支持: {', '.join(allowed_extensions)}"
        )
    
    # 生成唯一文件ID
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{file_ext}"
    file_path = DATA_DIR / filename
    
    # 保存文件
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 读取基本信息
    try:
        if file_ext == ".csv":
            import pandas as pd
            df = pd.read_csv(file_path)
        else:
            import pandas as pd
            df = pd.read_excel(file_path)
        
        info = {
            "file_id": file_id,
            "filename": file.filename,
            "original_name": file.filename,
            "size": len(content),
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "path": str(file_path)
        }
    except Exception as e:
        info = {
            "file_id": file_id,
            "filename": file.filename,
            "original_name": file.filename,
            "size": len(content),
            "path": str(file_path),
            "error": str(e)
        }
    
    return info


@app.post("/analyze")
async def analyze_data(request: AnalysisRequest):
    """
    启动数据分析任务
    返回流式响应
    """
    if not request.goal:
        raise HTTPException(status_code=400, detail="分析目标不能为空")

    if not request.llm_config:
        raise HTTPException(status_code=400, detail="模型配置不能为空")

    base_url = request.llm_config.get("base_url")
    api_key = request.llm_config.get("api_key")
    model_name = request.llm_config.get("model_name", "gpt-4o")
    
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="base_url 和 api_key 不能为空")
    
    # 获取数据信息
    data_info = None
    if request.file_id:
        file_path = None
        for ext in [".xlsx", ".xls", ".csv"]:
            potential_path = DATA_DIR / f"{request.file_id}{ext}"
            if potential_path.exists():
                file_path = potential_path
                break
        
        if file_path:
            import pandas as pd
            if file_path.suffix == ".csv":
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            data_info = {
                "file_id": request.file_id,
                "path": str(file_path),
                "filename": file_path.name,
                "rows": len(df),
                "columns": list(df.columns),
                "sample": df.head(5).to_dict(orient="records")
            }
    
    # 创建 Agent
    agent = DataAnalysisAgent(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name
    )
    
    return StreamingResponse(
        generate_analysis_stream(agent, request.goal, data_info),
        media_type="text/event-stream"
    )


@app.get("/files/{file_id}")
async def get_file_info(file_id: str):
    """获取已上传文件的信息"""
    file_path = None
    for ext in [".xlsx", ".xls", ".csv"]:
        potential_path = DATA_DIR / f"{file_id}{ext}"
        if potential_path.exists():
            file_path = potential_path
            break
    
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    import pandas as pd
    if file_path.suffix == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
    
    return {
        "file_id": file_id,
        "filename": file_path.name,
        "rows": len(df),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "sample": df.head(10).to_dict(orient="records"),
        "describe": df.describe().to_dict()
    }


@app.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """删除已上传的文件"""
    deleted = False
    for ext in [".xlsx", ".xls", ".csv"]:
        file_path = DATA_DIR / f"{file_id}{ext}"
        if file_path.exists():
            file_path.unlink()
            deleted = True
            break
    
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return {"message": "文件已删除"}


@app.get("/outputs")
async def list_outputs():
    """列出所有输出文件"""
    outputs = []
    for f in OUTPUTS_DIR.glob("*"):
        outputs.append({
            "name": f.name,
            "size": f.stat().st_size if f.is_file() else 0,
            "modified": f.stat().st_mtime
        })
    return {"outputs": outputs}
