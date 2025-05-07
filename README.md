<!--
 * @Author: DengYH
 * @Date: 2025-05-06 19:58:38
-->
# Book Summary

本项目使用 Python 作为开发语言，对9本外文书籍，进行处理，提取出书籍中的精华内容并总结出5~7个关键点，每个关键点至少要有3段内容，不少于1000字。

## 安装

确保已安装 Python 和相关依赖包。可以通过以下步骤安装：

### 1. 克隆项目

```
git clone https://github.com/yourusername/book-summary-generator.git
cd BookSummary
```

### 2. 安装依赖
```
pip install -r require.txt
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