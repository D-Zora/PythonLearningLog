'''
Author: DengYH
Date: 2025-05-06 23:00:56
'''
import os

def generate_markdown(book_summary, output_path):
    title = book_summary["title"]
    key_ideas = book_summary["key_ideas"]

    md_lines = []

    # 1. 页面标题
    md_lines.append(f"# 📘 Key Ideas from *{title}*")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # 2. 目录部分
    md_lines.append("## 🧭 Key ideas in *" + title + "*\n")
    for i, idea in enumerate(key_ideas, start=1):
        md_lines.append(f"- [{i}. {idea['title']}](#key-idea-{i})")
    md_lines.append("\n---\n")

    # 3. 正文部分
    for i, idea in enumerate(key_ideas, start=1):
        md_lines.append(f"## 🔹 Key idea {i} of {len(key_ideas)} <a name='key-idea-{i}'></a>\n")
        md_lines.append(f"### ✨ {idea['title']}\n")

        for para in idea["content"]:
            md_lines.append(para.strip())
            md_lines.append("")  # 空行表示段落

        md_lines.append("---\n")

    # 保存
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"✅ Markdown saved to: {output_path}")
