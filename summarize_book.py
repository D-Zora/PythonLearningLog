import os
import nltk
from nltk.tokenize import sent_tokenize
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

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
        if len(supports) < per_key:
            supports += [p for p in paragraphs if p not in supports][:per_key - len(supports)]

        if len(key) > 80:
            short_title = key.strip().split(".")[0]
        else:
            short_title = key

        result.append({
            "title": key,
            "short_title": short_title.strip().rstrip('.') + '.',
            "content": supports
        })
    return result

def generate_introduction(text, max_sentences=15, max_chars=1000):
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = TextRankSummarizer()
    summary = summarizer(parser.document, max_sentences)

    selected = []
    total_chars = 0
    for sentence in summary:
        sentence_str = str(sentence)
        if total_chars + len(sentence_str) > max_chars:
            break
        selected.append(sentence_str)
        total_chars += len(sentence_str)

    return " ".join(selected)


def generate_markdown(book_summary, output_path):
    title = book_summary["title"]
    key_ideas = book_summary["key_ideas"]
    introduction = book_summary["introduction"]

    md_lines = []

    md_lines.append(f"# Key Ideas from *{title}*")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    md_lines.append("## Introduction")
    md_lines.append("")
    md_lines.append(f"{introduction}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    md_lines.append("## Table of Contents")
    md_lines.append("")
    for i, idea in enumerate(key_ideas, start=1):
        anchor = f"key-idea-{i}"
        short_title = idea['short_title']
        md_lines.append(f"- [Key Idea {i}: {short_title}](#{anchor})")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    for i, idea in enumerate(key_ideas, start=1):
        anchor = f"key-idea-{i}"
        md_lines.append(f"## Key Idea {i}: {idea['title']}")
        md_lines.append(f"<a name='{anchor}'></a>")
        md_lines.append("")
        for para in idea["content"]:
            md_lines.append(f"{para}")
            md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"文件已保存至: {output_path}")

def summarize_book(txt_path, output_path):
    text = read_book(txt_path)
    paragraphs = split_paragraphs(text)
    key_sentences = extract_key_sentences(text, count=6)
    key_ideas = find_supporting_paragraphs(key_sentences, paragraphs, per_key=3)
    intro = generate_introduction(text, max_sentences=20, max_chars=1000)

    book_summary = {
        "title": os.path.basename(txt_path).replace(".txt", ""),
        "introduction": intro,
        "key_ideas": key_ideas
    }

    generate_markdown(book_summary, output_path)

def batch_summarize(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for file in os.listdir(input_folder):
        if file.endswith('.txt'):
            in_path = os.path.join(input_folder, file)
            out_path = os.path.join(output_folder, file.replace('.txt', '_summary.md'))
            summarize_book(in_path, out_path)
            print(f'处理完成：{file}')


if __name__ == '__main__':
    input_folder = 'output_book'
    output_folder = 'book_summaries'
    batch_summarize(input_folder, output_folder)
