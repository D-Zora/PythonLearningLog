"""Backend package for tavily-company-research."""

import os
import sys
from pathlib import Path
import logging
from dotenv import load_dotenv

# 设置日志记录器
logger = logging.getLogger(__name__)

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    logger.info(f"Loading environment variables from {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
else:
    logger.warning(f".env file not found at {env_path}. Using system environment variables.")

# 检查是否设置了关键的环境变量
# 本地数据模式时注释掉 Tavily API 检查
# if not os.getenv("TAVILY_API_KEY"):
#     logger.warning("TAVILY_API_KEY environment variable is not set.")

if not os.getenv("OPENAI_API_KEY"):
    logger.warning("OPENAI_API_KEY environment variable is not set.")

#if not os.getenv("GEMINI_API_KEY"):
#    logger.warning("GEMINI_API_KEY environment variable is not set.")

from .graph import Graph

__all__ = ["Graph"]
