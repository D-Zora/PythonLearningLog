import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class LocalDataManager:
    """管理本地JSON数据的存储和读取"""
    
    def __init__(self, data_dir: str = "local_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        logger.info(f"Local data directory initialized at {self.data_dir}")
    
    async def get_site_extraction(self, url: str) -> Dict[str, Any]:
        """从本地数据中获取网站内容提取结果"""
        try:
            # 使用URL的域名作为文件名
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            safe_domain = "".join(c if c.isalnum() else "_" for c in domain)
            file_path = self.data_dir / f"{safe_domain}_site.json"
            
            if not file_path.exists():
                logger.info(f"No local site data found for {url}")
                return {"results": []}
            
            # 读取数据
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded site extraction data for {url} from {file_path}")
            return data
        except Exception as e:
            logger.error(f"Error loading site extraction data: {e}")
            return {"results": []}
    
    async def get_search_results(self, query: str, company: str = None) -> Dict[str, Any]:
        """从本地数据中获取搜索结果"""
        try:
            # 使用查询作为文件名
            safe_query = "".join(c if c.isalnum() else "_" for c in query)
            
            # 如果提供了公司名称，在公司子目录中查找
            if company:
                file_path = self.data_dir / company / f"{safe_query}.json"
            else:
                file_path = self.data_dir / f"{safe_query}.json"
            
            if not file_path.exists():
                logger.info(f"No local search data found for query '{query}' in {file_path}")
                return {"results": []}
            
            # 读取数据
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 将数据转换为标准格式，并强制设置 source 为 local_data
            results = []
            for url, doc in data.items():
                results.append({
                    "url": url,
                    "title": doc.get("title", ""),
                    "content": doc.get("content", ""),
                    "score": doc.get("score", 0.0),
                    "source": "local_data"  # 强制设置为 local_data，忽略原始数据中的 source
                })
            
            logger.info(f"Loaded search results for query '{query}' from {file_path}")
            return {"results": results}
        except Exception as e:
            logger.error(f"Error loading search results: {e}")
            return {"results": []}
    
    def save_search_results(self, company: str, query: str, results: Dict[str, Any]) -> None:
        """保存搜索结果到本地JSON文件"""
        try:
            # 创建公司目录
            company_dir = self.data_dir / company
            company_dir.mkdir(exist_ok=True)
            
            # 使用查询作为文件名（进行简单清理）
            safe_query = "".join(c if c.isalnum() else "_" for c in query)
            file_path = company_dir / f"{safe_query}.json"
            
            # 保存数据
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved search results for query '{query}' to {file_path}")
        except Exception as e:
            logger.error(f"Error saving search results: {e}")
            raise
    
    def load_search_results(self, company: str, query: str) -> Optional[Dict[str, Any]]:
        """从本地JSON文件加载搜索结果"""
        try:
            # 构建文件路径
            safe_query = "".join(c if c.isalnum() else "_" for c in query)
            file_path = self.data_dir / company / f"{safe_query}.json"
            
            if not file_path.exists():
                logger.info(f"No local data found for query '{query}'")
                return None
            
            # 读取数据
            with open(file_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            logger.info(f"Loaded search results for query '{query}' from {file_path}")
            return results
        except Exception as e:
            logger.error(f"Error loading search results: {e}")
            return None
    
    def has_local_data(self, company: str, query: str) -> bool:
        """检查是否存在本地数据"""
        safe_query = "".join(c if c.isalnum() else "_" for c in query)
        file_path = self.data_dir / company / f"{safe_query}.json"
        return file_path.exists() 