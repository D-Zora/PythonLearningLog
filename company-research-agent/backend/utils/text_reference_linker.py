import re
from typing import Dict, Any, List, Tuple, Optional
import logging
from urllib.parse import urlparse
from .references import clean_title
import json
from pathlib import Path
from backend.utils.local_data import LocalDataManager

logger = logging.getLogger(__name__)

class TextReferenceLinker:
    """处理文本匹配和添加来源链接的工具类"""
    
    # 定义匹配模式，使用更精确的模式
    PATTERNS = {
        # 财务数据
        'financial_metrics': [
            r'(?:revenue|sales|income|profit|earnings|growth|increase|decrease|loss)\s*(?:of|at|was|is)?\s*\$?\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:USD|dollars)?(?:\s*(?:in|for|during))?\s*(?:Q[1-4]|quarter|year|month|week)?(?:\s*\d{4})?',
            r'\d+(?:\.\d+)?%\s*(?:increase|decrease|growth|decline|up|down)(?:\s*(?:in|of|for))?\s*(?:revenue|sales|income|profit|earnings|market share|market value)',
            r'\$?\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:USD|dollars)?(?:\s*(?:in|of|for))?\s*(?:revenue|sales|income|profit|earnings|growth|increase|decrease|loss)',
        ],
        # 市场份额数据
        'market_share': [
            r'\d+(?:\.\d+)?%\s*(?:of|in)?\s*(?:market share|market)(?:\s*(?:in|for|during))?\s*(?:Q[1-4]|quarter|year|month|week)?(?:\s*\d{4})?',
            r'(?:market share|market value|market size)\s*(?:of|is|was|at)?\s*\$?\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:USD|dollars)?',
        ],
        # 销售数据
        'sales_data': [
            r'(?:sold|delivered|produced)\s*\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:units|vehicles|cars)?(?:\s*(?:in|for|during))?\s*(?:Q[1-4]|quarter|year|month|week)?(?:\s*\d{4})?',
            r'\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:units|vehicles|cars)?(?:\s*(?:sold|delivered|produced))(?:\s*(?:in|for|during))?\s*(?:Q[1-4]|quarter|year|month|week)?(?:\s*\d{4})?',
        ],
        # 业务战略数据
        'business_strategy': [
            r'(?:launched|announced|introduced|released)\s+(?:new|the|a)?\s*(?:product|service|feature|strategy|initiative|partnership|acquisition)',
            r'(?:expanding|entering|launching)\s+(?:into|in|new)?\s*(?:market|region|country|segment)',
            r'(?:investing|invested|investment)\s+(?:in|into|of)?\s*\$?\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:USD|dollars)?',
        ],
        # 技术数据
        'technical_metrics': [
            r'(?:efficiency|performance|capacity|range|speed|power|output)\s*(?:of|at|is|was)?\s*\d+(?:\.\d+)?(?:\s*(?:kWh|kW|mph|km/h|miles|kilometers|percent|%))?',
            r'\d+(?:\.\d+)?(?:\s*(?:kWh|kW|mph|km/h|miles|kilometers|percent|%))?\s*(?:efficiency|performance|capacity|range|speed|power|output)',
        ]
    }
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.url_to_number = {}  # URL -> number
        self.number_to_url = {}  # number -> URL
        self.current_ref_number = 0
        self.data_to_urls = {}
        self.url_to_title = {}  # 存储URL到标题的映射
        self.data_dir = data_dir  # 本地数据目录
        self.content_cache = {}  # 缓存已加载的内容
    
    def _get_or_create_ref_number(self, url: str) -> int:
        """获取或创建URL的引用编号"""
        if url not in self.url_to_number:
            self.current_ref_number += 1
            self.url_to_number[url] = self.current_ref_number
            self.number_to_url[self.current_ref_number] = url
        return self.url_to_number[url]
    
    def add_data_source(self, data: str, url: str, title: str = "", score: float = 0.0) -> None:
        """添加数据源映射，包含标题和相关性分数"""
        if data and url:
            if data not in self.data_to_urls:
                self.data_to_urls[data] = []
            # 存储URL、标题和分数
            self.data_to_urls[data].append((url, title, score))
            # 存储URL到标题的映射
            if title:
                self.url_to_title[url] = title
            # 确保URL有引用编号
            self._get_or_create_ref_number(url)
    
    def _sort_urls_by_score(self, urls_with_info: List[Tuple[str, str, float]]) -> List[Tuple[str, str]]:
        """根据分数对URL进行排序，返回URL和标题的元组列表"""
        sorted_items = sorted(urls_with_info, key=lambda x: x[2], reverse=True)
        return [(url, title) for url, title, _ in sorted_items]
    
    def _create_reference_mark(self, url: str, title: str = "") -> str:
        """创建引用标记，使用更紧凑的格式"""
        ref_num = self._get_or_create_ref_number(url)
        if not title:
            title = self.url_to_title.get(url, urlparse(url).netloc)
        # 使用更紧凑的格式：[n]
        return f'[{ref_num}]'
    
    async def process_text(self, text: str, context: Dict[str, Any]) -> str:
        """处理文本，添加引用标记
        
        Args:
            text: 要处理的文本
            context: 包含数据源的上下文信息
            
        Returns:
            str: 处理后的文本，包含引用标记
        """
        if not text or not context:
            return text
            
        # 存储找到的数据及其位置
        matches = []
        
        # 使用预定义的正则表达式模式匹配数据
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    data = match.group(0)  # 提取匹配的数据
                    if data in self.data_to_urls:
                        matches.append((match.start(), match.end(), data))
        
        # 按位置排序匹配结果
        matches.sort(key=lambda x: x[0])
        
        # 从后向前插入引用标记（避免位置偏移）
        result = text
        for start, end, data in reversed(matches):
            urls_with_info = self.data_to_urls[data]
            # 根据分数排序URL
            sorted_urls = self._sort_urls_by_score(urls_with_info)
            # 为每个URL创建引用标记
            ref_marks = []
            for url, title in sorted_urls:
                ref_mark = self._create_reference_mark(url, title)
                ref_marks.append(ref_mark)
            # 将所有引用标记组合在一起，使用更紧凑的格式
            ref_mark = ''.join(ref_marks)
            # 在数据后面添加引用标记，使用上标格式
            result = result[:end] + '<sup>' + ref_mark + '</sup>' + result[end:]
        
        return result
    
    def get_references_section(self) -> str:
        """生成引用部分，使用更规范的格式
        
        Returns:
            str: 格式化的引用部分文本
        """
        if not self.url_to_number:
            return ""
        
        ref_text = "\n\n## 参考文献\n\n"
        # 使用 number_to_url 字典，按数字顺序排序
        for num in sorted(self.number_to_url.keys()):
            url = self.number_to_url[num]
            title = self.url_to_title.get(url, "")
            domain = urlparse(url).netloc
            
            # 使用更规范的引用格式
            if title:
                ref_text += f"{num}. {title}. {domain}. {url}\n"
            else:
                ref_text += f"{num}. {domain}. {url}\n"
        
        return ref_text
    
    def reset(self) -> None:
        """重置链接器状态"""
        self.url_to_number.clear()
        self.number_to_url.clear()
        self.data_to_urls.clear()
        self.url_to_title.clear()
        self.current_ref_number = 0
    
    def load_local_content(self, company: str = None) -> None:
        """从本地JSON文件加载内容
        
        Args:
            company: 公司名称，如果提供则只加载该公司目录下的文件
        """
        if not self.data_dir:
            logger.warning("No data directory specified for loading local content")
            return
            
        try:
            # 使用 LocalDataManager 获取数据
            local_data_manager = LocalDataManager(data_dir=self.data_dir)
            
            # 获取公司目录下的所有 JSON 文件
            company_dir = self.data_dir / company if company else self.data_dir
            if not company_dir.exists():
                logger.warning(f"Company directory not found: {company_dir}")
                return
                
            # 遍历所有 JSON 文件
            for json_file in company_dir.glob("**/*.json"):
                try:
                    # 读取 JSON 文件
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 处理数据并添加到引用系统
                    for url, doc in data.items():
                        content = doc.get("content", "")
                        title = doc.get("title", "")
                        score = doc.get("score", 0.0)
                        
                        if content:
                            segments = self._split_content_into_segments(content)
                            for segment in segments:
                                self.add_data_source(segment, url, title, score)
                            
                            self.content_cache[url] = {
                                "content": content,
                                "title": title,
                                "score": score
                            }
                    
                    logger.info(f"Successfully loaded content from {json_file}")
                except Exception as e:
                    logger.error(f"Error loading file {json_file}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error loading local content: {e}")
    
    def _split_content_into_segments(self, content: str, min_length: int = 50) -> List[str]:
        """将内容分割成有意义的段落
        
        Args:
            content: 要分割的内容
            min_length: 最小段落长度
            
        Returns:
            List[str]: 段落列表
        """
        # 使用多种分隔符分割内容
        segments = []
        # 按句子分割
        sentences = re.split(r'(?<=[.!?])\s+', content)
        current_segment = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 如果当前段落加上新句子超过最小长度，保存当前段落
            if current_length + len(sentence) > min_length and current_segment:
                segments.append(' '.join(current_segment))
                current_segment = []
                current_length = 0
            
            current_segment.append(sentence)
            current_length += len(sentence)
        
        # 添加最后一个段落
        if current_segment:
            segments.append(' '.join(current_segment))
        
        return segments
    
    def find_matching_content(self, text: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """查找与给定文本匹配的内容
        Args:
            text: 要匹配的文本
            threshold: 匹配阈值（0-1之间）
            
        Returns:
            List[Dict[str, Any]]: 匹配结果列表，每个结果包含url、title、score和匹配内容
        """
        matches = []
        
        # 首先使用正则表达式模式匹配
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    data = match.group(0)
                    if data in self.data_to_urls:
                        urls_with_info = self.data_to_urls[data]
                        for url, title, score in urls_with_info:
                            matches.append({
                                "url": url,
                                "title": title,
                                "score": score,
                                "matched_content": data,
                                "match_type": "pattern"
                            })
        
        # 然后进行模糊匹配
        for url, cache_data in self.content_cache.items():
            content = cache_data["content"]
            title = cache_data["title"]
            score = cache_data["score"]
            
            # 计算文本相似度（这里使用简单的包含关系，可以替换为更复杂的相似度算法）
            if text.lower() in content.lower():
                similarity = len(text) / len(content)  # 简单的相似度计算
                if similarity >= threshold:
                    matches.append({
                        "url": url,
                        "title": title,
                        "score": score * similarity,  # 调整分数
                        "matched_content": content,
                        "match_type": "fuzzy"
                    })
        
        # 按分数排序
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches
    
    def add_tavily_results(self, results: List[Dict[str, Any]]) -> None:
        """添加Tavily API搜索结果
        
        Args:
            results: Tavily API返回的结果列表
        """
        for result in results:
            url = result.get("url")
            content = result.get("content", "")
            title = result.get("title", "")
            score = result.get("score", 0.0)
            
            if content and url:
                # 将内容分段并添加到数据源
                segments = self._split_content_into_segments(content)
                for segment in segments:
                    self.add_data_source(segment, url, title, score)
                
                # 缓存完整内容
                self.content_cache[url] = {
                    "content": content,
                    "title": title,
                    "score": score
                } 