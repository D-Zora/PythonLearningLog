<!--
 * @Author: DengYH
 * @Date: 2025-05-06 19:58:38
-->
# Book Summary Generator

本项目是一个自动生成书籍摘要和 Markdown 格式总结的工具。它通过提取书籍中的关键句子和段落来生成一个简洁的书籍概述，并使用 Markdown 格式生成书籍的摘要页面。该工具适用于批量处理多个书籍文件，自动提取关键内容，并以清晰的格式呈现。

## 功能

1. **提取书籍中的关键句子**：使用 TextRank 算法提取书籍中的关键句子。
2. **生成简洁的书籍摘要**：从提取的关键句子中找到支持内容，生成书籍的关键点。
3. **自动生成简介**：提取书籍前几段作为简介，并自动总结书籍内容。
4. **生成 Markdown 文件**：将书籍的简介和关键句相关内容生成具有左右结构的 Markdown 页面。
5. **批量处理**：支持批量处理多个文本文件，自动为每个文件生成摘要。

## 安装

确保已安装 Python 和相关依赖包。可以通过以下步骤安装：

### 1. 克隆项目

```
git clone https://github.com/yourusername/book-summary-generator.git
cd book-summary-generator
```

### 2. 安装依赖
```
pip install -r requirements.txt
```

### 3. 下载 NLTK 数据
```
python -m nltk.downloader punkt
```

## 使用
### 1. 单个书籍摘要生成
在 summarize_book 函数中传入输入文本文件路径和输出 Markdown 文件路径，执行代码即可生成摘要。
```
summarize_book('path_to_book.txt', 'path_to_output.md')
```

### 2. 批量处理书籍
将书籍文件放入指定文件夹 input_folder 中，运行 batch_summarize 函数，工具将自动为每本书生成摘要。
```
input_folder = '输入文本文件夹'
output_folder = '输出摘要文件夹'
batch_summarize(input_folder, output_folder)
```

## 目录结构
```
book-summary-generator/
│
├── main.py               # 主要脚本，包含所有函数定义和执行逻辑
├── requirements.txt      # 项目依赖的第三方库
├── README.md             # 项目的说明文档
└── output_book/          # 存放输入的书籍文本文件
└── book_summaries/       # 存放输出的 Markdown 摘要文件
```