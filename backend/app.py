"""
DataReportNew 后端入口模块

启动方式（需在项目根目录 DataReportNew/）:
    python -m backend.app
或：
    uvicorn backend.app:app --reload
"""
from .main import app

__all__ = ["app"]