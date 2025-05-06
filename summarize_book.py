import nltk
import os
from nltk.tokenize import sent_tokenize
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

# 下载 punkt 分词模型（只需一次）
nltk.download('punkt')

# 读取txt文件
def read_book(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        return f.read()

# 拆分为句子与段落
def split_sentences(text):
    return sent_tokenize(text)

def split_paragraphs(text):
    return [p.strip() for p in text.split('\n') if len(p.strip()) > 50]

# 提取关键句（作为标题）
def get_key(text, count=6):
    parser = PlaintextParser.from_string(text, Tokenizer('english'))
    summarizer = TextRankSummarizer()
    summary = summarizer(parser.document, count)
    return [str(sentence) for sentence in summary]

# 每个关键句匹配相关段落（正文）
def find_support(key_sentences, paragraphs, per_key=3):
    result = []
    for key in key_sentences:
        support = []
        for p in paragraphs:
            if key.split()[0] in p and len(p) > 100:
                support.append(p)
                if len(support) >= per_key:
                    break
        result.append({
            "title": key,
            "content": support
        })
    return result

# Markdown 美化输出
def generate_markdown(book_title, key_ideas, output_path):
    md_lines = []

    # 1. 页面标题
    md_lines.append(f"# 📘 Key Ideas from *{book_title}*")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # 2. 目录部分
    md_lines.append(f"## 🧭 Key ideas in *{book_title}*\n")
    for i, idea in enumerate(key_ideas, start=1):
        md_lines.append(f"- [{i}. {idea['title']}](#key-idea-{i})")
    md_lines.append("\n---\n")

    # 3. 正文部分
    for i, idea in enumerate(key_ideas, start=1):
        md_lines.append(f"## 🔹 Key idea {i} of {len(key_ideas)} <a name='key-idea-{i}'></a>\n")
        md_lines.append(f"### ✨ {idea['title']}\n")
        md_lines.append("")
        for para in idea["content"]:
            md_lines.append(para.strip())
            md_lines.append("")
        md_lines.append("---\n")

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"✅ Markdown saved to: {output_path}")

# 单个文件处理逻辑
def summarize_book(txt_path, output_path):
    text = read_book(txt_path)
    paragraphs = split_paragraphs(text)
    key_sentences = get_key(text, count=6)
    key_ideas = find_support(key_sentences, paragraphs)
    book_title = os.path.splitext(os.path.basename(txt_path))[0].replace('_', ' ')
    generate_markdown(book_title, key_ideas, output_path)

# 批量处理所有 txt
def batch_summarize(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for file in os.listdir(input_folder):
        if file.endswith('.txt'):
            in_path = os.path.join(input_folder, file)
            out_path = os.path.join(output_folder, file.replace('.txt', '_summary.md'))
            summarize_book(in_path, out_path)
            print(f"📄 处理完成：{file}")

# 主程序入口
if __name__ == '__main__':
    input_folder = 'output_book'
    output_folder = 'book_summaries'
    batch_summarize(input_folder, output_folder)
