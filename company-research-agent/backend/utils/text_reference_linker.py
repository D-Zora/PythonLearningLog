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
            r'\$?\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:USD|dollars)?',  # 匹配任何金额
            r'\d+(?:\.\d+)?%\s*(?:increase|decrease|growth|decline|up|down)',  # 匹配任何百分比变化
            r'\d+(?:\.\d+)?%\s*(?:of|in)?\s*(?:market share|market)',  # 匹配市场份额百分比
        ],
        # 销售数据
        'sales_data': [
            r'\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:units|vehicles|cars)',  # 匹配销售数量
            r'\d+(?:\.\d+)?(?:B|M|K)?(?:\s*(?:billion|million|thousand))?\s*(?:sold|delivered|produced)',  # 匹配生产/销售数量
        ],
        # 技术数据
        'technical_metrics': [
            r'\d+(?:\.\d+)?(?:\s*(?:kWh|kW|mph|km/h|miles|kilometers|percent|%))',  # 匹配技术指标
        ],
        # 时间数据
        'time_data': [
            r'\d{4}',  # 匹配年份
            r'Q[1-4]\s*\d{4}',  # 匹配季度
        ],
        # 通用数值
        'general_numbers': [
            r'\d+(?:\.\d+)?',  # 匹配任何数字
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
        self.url_to_ref = {}  # URL -> reference number
        self.ref_to_url = {}  # reference number -> URL
        self.ref_to_title = {}  # reference number -> title
        
        # 记录正则表达式模式
        logger.info("Initialized TextReferenceLinker with patterns:")
        for category, patterns in self.PATTERNS.items():
            logger.info(f"Category '{category}' has {len(patterns)} patterns:")
            for i, pattern in enumerate(patterns, 1):
                logger.debug(f"  Pattern {i}: {pattern}")
    
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
            ref_num = self._get_or_create_ref_number(url)
            logger.info(f"Added data source: data='{data[:50]}...', url='{url}', title='{title}', score={score}, ref_num={ref_num}")
            logger.debug(f"Current data_to_urls size: {len(self.data_to_urls)}, url_to_number size: {len(self.url_to_number)}")
    
    def _sort_urls_by_score(self, urls_with_info: List[Tuple[str, str, float]]) -> List[Tuple[str, str]]:
        """根据分数对URL进行排序，返回URL和标题的元组列表"""
        sorted_items = sorted(urls_with_info, key=lambda x: x[2], reverse=True)
        return [(url, title) for url, title, _ in sorted_items]
    
    def _create_reference_mark(self, url: str, title: str) -> str:
        """创建引用标记，使用纯 Markdown 脚注格式"""
        if url not in self.url_to_ref:
            self.url_to_ref[url] = len(self.url_to_ref) + 1
            self.ref_to_url[self.url_to_ref[url]] = url
            self.ref_to_title[self.url_to_ref[url]] = title
            logger.info(f"Created reference mark: url='{url}', title='{title}', mark='[^{self.url_to_ref[url]}]'")
        # 使用纯 Markdown 脚注格式
        ref_num = self.url_to_ref[url]
        return f'[^{ref_num}]'
    
    def process_text(self, text: str) -> str:
        """处理文本，添加引用标记"""
        logger.info(f"Processing text: {text[:100]}...")
        logger.info(f"Current data_to_urls size: {len(self.data_to_urls)}")
        
        # 存储所有匹配结果
        matches = []
        
        # 首先使用正则表达式匹配数值数据
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group(0)
                    # 检查这个数值是否在数据源中
                    for data, urls in self.data_to_urls.items():
                        if matched_text in data:
                            # 获取匹配文本的位置
                            pos = match.start()
                            end_pos = match.end()
                            
                            # 检查这个位置是否已经有引用标记
                            has_ref = False
                            for m in matches:
                                if abs(m[0] - pos) < 5 or abs(m[1] - end_pos) < 5:
                                    has_ref = True
                                    break
                            
                            if not has_ref:
                                # 为每个匹配位置创建引用标记
                                ref_nums = set()
                                for url, title, score in urls:
                                    if url not in self.url_to_ref:
                                        self.url_to_ref[url] = len(self.url_to_ref) + 1
                                        self.ref_to_url[self.url_to_ref[url]] = url
                                        self.ref_to_title[self.url_to_ref[url]] = title
                                    ref_nums.add(self.url_to_ref[url])
                                
                                if ref_nums:
                                    # 创建单个引用标记，包含所有引用编号
                                    ref_nums_str = ','.join(map(str, sorted(ref_nums)))
                                    mark = f'[^{ref_nums_str}]'  # 移除多余的空格
                                    matches.append((pos, end_pos, mark))
                                    logger.debug(f"Found match: '{matched_text}' -> {mark} at position {pos}")
        
        # 按位置排序匹配结果
        matches.sort(key=lambda x: x[0])
        
        # 合并相邻的引用标记
        merged_matches = []
        if matches:
            current_match = list(matches[0])
            for match in matches[1:]:
                if match[0] <= current_match[1] + 5:  # 允许引用标记之间有5个字符的间隔
                    # 合并引用标记，确保不重复
                    current_refs = set(map(int, re.findall(r'\[\^(\d+(?:,\d+)*)\]', current_match[2])[0].split(',')))
                    new_refs = set(map(int, re.findall(r'\[\^(\d+(?:,\d+)*)\]', match[2])[0].split(',')))
                    combined_refs = sorted(list(current_refs.union(new_refs)))
                    ref_nums_str = ','.join(map(str, combined_refs))
                    current_match[2] = f'[^{ref_nums_str}]'  # 移除多余的空格
                    current_match[1] = max(current_match[1], match[1])
                else:
                    merged_matches.append(tuple(current_match))
                    current_match = list(match)
            merged_matches.append(tuple(current_match))
        
        # 从后向前替换，避免位置偏移
        result = text
        for start, end, mark in reversed(merged_matches):
            # 在匹配文本后添加引用标记，确保标记前后有适当的空格
            if end < len(result) and result[end].isalnum():
                # 如果后面是字母或数字，添加空格
                result = result[:end] + " " + mark + " " + result[end:]
            else:
                # 如果后面是标点符号或其他字符，不添加空格
                result = result[:end] + mark + result[end:]
        
        # 清理可能存在的 HTML sup 标签
        result = re.sub(r'<sup>\[.*?\]</sup>', '', result)
        
        # 优化引用标记的格式
        # 1. 移除引用标记前后的多余空格
        result = re.sub(r'\s+\[\^(\d+(?:,\d+)*)\]\s+', r' [^\1] ', result)
        # 2. 确保引用标记和数字之间有空格
        result = re.sub(r'\[\^(\d+(?:,\d+)*)\](\d)', r'[^\1] \2', result)
        # 3. 确保引用标记和标点符号之间有空格
        result = re.sub(r'\[\^(\d+(?:,\d+)*)\]([.,;:])', r'[^\1] \2', result)
        # 4. 移除引用标记之间的多余空格
        result = re.sub(r'\[\^(\d+(?:,\d+)*)\]\s+\[\^(\d+(?:,\d+)*)\]', r'[^\1][^\2]', result)
        # 5. 确保引用标记和括号之间有空格
        result = re.sub(r'\[\^(\d+(?:,\d+)*)\]\(', r'[^\1] (', result)
        result = re.sub(r'\)\[\^(\d+(?:,\d+)*)\]', r') [^\1]', result)
        
        # 添加参考文献部分
        references = self.get_references_section()
        if references:
            result += references
        
        logger.info(f"Found {len(matches)} matches in total")
        return result
    
    def get_references_section(self) -> str:
        """生成引用部分，使用纯Markdown格式
        
        Returns:
            str: 格式化的引用部分文本
        """
        if not self.url_to_ref:
            return ""
        
        ref_text = "\n\n## References\n\n"  # 使用英文标题
        # 使用 ref_to_url 字典，按数字顺序排序
        for num in sorted(self.ref_to_url.keys()):
            url = self.ref_to_url[num]
            title = self.ref_to_title.get(url, "")
            domain = urlparse(url).netloc
            
            # 使用纯Markdown格式
            if title:
                # 如果标题太长，截断并添加省略号
                display_title = title if len(title) <= 100 else title[:97] + "..."
                ref_text += f'[^{num}]: [{display_title}]({url}) - {domain}\n'
            else:
                ref_text += f'[^{num}]: [{domain}]({url})\n'
        
        return ref_text
    
    def reset(self) -> None:
        """重置链接器状态"""
        self.url_to_number.clear()
        self.number_to_url.clear()
        self.data_to_urls.clear()
        self.url_to_title.clear()
        self.current_ref_number = 0
        self.url_to_ref.clear()
        self.ref_to_url.clear()
        self.ref_to_title.clear()
    
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