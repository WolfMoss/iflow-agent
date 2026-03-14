# -*- coding: utf-8 -*-
"""启动入口：通过 uvicorn 运行 FastAPI 应用。"""
import uvicorn

from core.config import settings
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
