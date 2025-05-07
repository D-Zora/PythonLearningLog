import os
import nltk
from nltk.tokenize import sent_tokenize
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

nltk.download('punkt')

def read_book(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    return text

def split_paragraphs(text):
    return [p.strip() for p in text.split('\n') if len(p.strip()) > 50]


def extract_key_sentences(text, count=7):
    parser = PlaintextParser.from_string(text, Tokenizer('english'))
    summarizer = TextRankSummarizer()
    summary = summarizer(parser.document, count)
    return [str(sentence) for sentence in summary]


# 从段落中提取与关键句相关的内容（用于生成详细内容）
def find_supporting_paragraphs(key_sentences, paragraphs, per_key=3):
    result = []
    for key in key_sentences:
        supports = []
        for para in paragraphs:
            if key.split()[0] in para and len(para) > 100:
                supports.append(para.strip())
                if len(supports) >= per_key:
                    break
        # 如果匹配不够，用其他段落补足
        if len(supports) < per_key:
            supports += [p for p in paragraphs if p not in supports][:per_key - len(supports)]
        result.append({"title": key,
                       "short_title": ' '.join(key.strip().split()[:6]) + "...",
                       "content": supports})
    return result


# 自动生成简介 Introduction（取前几段 + 总体总结）
def generate_introduction(paragraphs, count=3):
    intro = "\n\n".join(paragraphs[:count])
    return intro


# 生成 Markdown 布局（左右结构）
def generate_markdown(book_summary, output_path):
    title = book_summary["title"]
    key_ideas = book_summary["key_ideas"]
    introduction = book_summary["introduction"]

    md_lines = []
    md_lines.append("<div style='display: flex;'>")

    # === 右边导航栏 ===
    md_lines.append("<div style='width: 25%; padding-right: 20px; border-right: 1px solid #ccc;'>")
    md_lines.append(f"<h2>🔹 Key Ideas in <i>{title}</i></h2>")
    md_lines.append("<ul>")
    for i, idea in enumerate(key_ideas, start=1):
        md_lines.append(f"<li><a href='#key-idea-{i}'>{idea['short_title']}</a></li>")
    md_lines.append("</ul>")
    md_lines.append("</div>")

    # === 左边正文内容 ===
    md_lines.append("<div style='width: 75%; padding-left: 20px;'>")
    md_lines.append(f"<h1>📘 Key Ideas from <i>{title}</i></h1>")
    md_lines.append("<hr>")
    md_lines.append("<h2>📖 Introduction</h2>")
    md_lines.append(f"<p>{introduction}</p>")
    md_lines.append("<hr>")

    for i, idea in enumerate(key_ideas, start=1):
        md_lines.append(f"<h2 id='key-idea-{i}'>🔸 Key Idea {i}: {idea['title']}</h2>")
        for para in idea["content"]:
            md_lines.append(f"<p>{para}</p>")
        md_lines.append("<hr>")

    md_lines.append("</div>")  # end of left content
    md_lines.append("</div>")  # end of container

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"✅ Markdown saved to: {output_path}")


# 单书摘要生成逻辑
def summarize_book(txt_path, output_path):
    text = read_book(txt_path)
    paragraphs = split_paragraphs(text)
    key_sentences = extract_key_sentences(text, count=6)
    key_ideas = find_supporting_paragraphs(key_sentences, paragraphs)
    intro = generate_introduction(paragraphs, count=3)

    book_summary = {
        "title": os.path.basename(txt_path).replace(".txt", ""),
        "introduction": intro,
        "key_ideas": key_ideas
    }

    generate_markdown(book_summary, output_path)


# 批量处理
def batch_summarize(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for file in os.listdir(input_folder):
        if file.endswith('.txt'):
            in_path = os.path.join(input_folder, file)
            out_path = os.path.join(output_folder, file.replace('.txt', '_summary.md'))
            summarize_book(in_path, out_path)
            print(f'✅ 处理完成：{file}')


if __name__ == '__main__':
    input_folder = 'output_book'       # 输入文本文件夹
    output_folder = 'book_summaries'   # 输出 Markdown 文件夹
    batch_summarize(input_folder, output_folder)
