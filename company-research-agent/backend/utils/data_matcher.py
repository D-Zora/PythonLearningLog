import re
import logging
from typing import Dict, List, Tuple, Any
from urllib.parse import urlparse
from collections import defaultdict

logger = logging.getLogger(__name__)

class DataMatcher:
    """处理数据匹配和引用标记的插入"""
    
    def __init__(self):
        # 存储URL到编号的映射
        self.url_to_number = {}
        # 存储数据到URL的映射
        self.data_to_urls = defaultdict(list)
        # 当前最大引用编号
        self.current_ref_number = 0
    
    def _extract_domain(self, url: str) -> str:
        """从URL中提取域名"""
        try:
            return urlparse(url).netloc
        except:
            return url
    
    def _get_or_create_ref_number(self, url: str) -> int:
        """获取或创建URL的引用编号"""
        if url not in self.url_to_number:
            self.current_ref_number += 1
            self.url_to_number[url] = self.current_ref_number
        return self.url_to_number[url]
    
    def add_data_source(self, data: str, url: str) -> None:
        """添加数据源映射"""
        if data and url:
            self.data_to_urls[data].append(url)
            # 确保URL有引用编号
            self._get_or_create_ref_number(url)
    
    def process_paragraph(self, paragraph: str, patterns: List[str]) -> Tuple[str, Dict[int, str]]:
        """处理段落，添加引用标记
        
        Args:
            paragraph: 要处理的段落文本
            patterns: 正则表达式模式列表，用于匹配数据
            
        Returns:
            Tuple[str, Dict[int, str]]: 
                - 处理后的段落文本（包含引用标记）
                - 引用编号到URL的映射字典
        """
        if not paragraph or not patterns:
            return paragraph, {}
        
        # 存储找到的数据及其位置
        matches = []
        
        # 使用所有模式匹配数据
        for pattern in patterns:
            for match in re.finditer(pattern, paragraph, re.IGNORECASE):
                data = match.group(0)
                if data in self.data_to_urls:
                    matches.append((match.start(), match.end(), data))
        
        # 按位置排序匹配结果
        matches.sort(key=lambda x: x[0])
        
        # 从后向前插入引用标记（避免位置偏移）
        result = paragraph
        for start, end, data in reversed(matches):
            urls = self.data_to_urls[data]
            # 为每个URL创建可点击的引用标记
            ref_marks = []
            for url in urls:
                ref_num = self._get_or_create_ref_number(url)
                # 使用Markdown链接格式 [n](url)，确保格式正确
                ref_marks.append(f'[{ref_num}]({url})')
            # 将所有引用标记组合在一起，确保它们之间有空格
            ref_mark = ' '.join(ref_marks)
            # 在数据后面添加一个空格，然后添加引用标记
            result = result[:end] + ' ' + ref_mark + result[end:]
        
        # 创建引用映射
        ref_map = {num: url for url, num in self.url_to_number.items()}
        
        # 清理可能的多余空格
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result, ref_map
    
    def get_references_section(self, ref_map: Dict[int, str]) -> str:
        """生成引用部分
        
        Args:
            ref_map: 引用编号到URL的映射字典
            
        Returns:
            str: 格式化的引用部分文本
        """
        if not ref_map:
            return ""
        
        ref_text = "\n\n## References\n"
        for num in sorted(ref_map.keys()):
            url = ref_map[num]
            domain = self._extract_domain(url)
            # 使用Markdown链接格式
            ref_text += f"{num}. [{domain}]({url})\n"
        
        return ref_text
    
    def reset(self) -> None:
        """重置匹配器状态"""
        self.url_to_number.clear()
        self.data_to_urls.clear()
        self.current_ref_number = 0 