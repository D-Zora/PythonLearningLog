import re
from typing import Dict, Any, List, Tuple
import logging
from urllib.parse import urlparse
from .references import clean_title

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
        ],
        # 新增：日期数据
        'dates': [
            r'(?:Q[1-4]|quarter)\s*\d{4}',
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',
            r'\d{4}',
        ],
        # 新增：公司事件
        'company_events': [
            r'(?:announced|launched|introduced|released|acquired|partnered with|invested in)\s+(?:[A-Z][a-zA-Z\s]+)',
            r'(?:expansion|growth|development|innovation|breakthrough)\s+(?:in|of|for)\s+(?:[A-Z][a-zA-Z\s]+)',
        ]
    }
    
    def __init__(self):
        self.url_to_number = {}
        self.current_ref_number = 0
        self.data_to_urls = {}
        self.url_to_title = {}  # 新增：存储URL到标题的映射
    
    def _get_or_create_ref_number(self, url: str) -> int:
        """获取或创建URL的引用编号"""
        if url not in self.url_to_number:
            self.current_ref_number += 1
            self.url_to_number[url] = self.current_ref_number
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
        
        # 使用所有模式匹配数据
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    data = match.group(0)
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
        for num in sorted(self.url_to_number.keys()):
            url = self.url_to_number[num]
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
        self.data_to_urls.clear()
        self.url_to_title.clear()
        self.current_ref_number = 0 