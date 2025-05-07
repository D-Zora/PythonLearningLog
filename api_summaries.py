import os
from openai import OpenAI
import textwrap

# 你的 OpenAI API 密钥
client = OpenAI(api_key="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")

def generate_book_summary(content):
    # 系统提示词工程
    system_prompt = textwrap.dedent("""
    你是一位专业的内容架构师，请按照以下要求处理书籍内容：
    1. 生成5~7个核心观点，每个观点包含：
       - 理论框架（100-150字）
       - 实证案例（具体案例说明）
       - 数据支撑（引用书中具体数据）
    2. 使用带锚点的Markdown格式
    3. 包含理论模型可视化代码块
    """)

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ],
        temperature=0.3,
        max_tokens=3000,
        top_p=0.9
    )
    return response.choices[0].message.content

# 从TXT文件中读取内容
def read_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# 遍历文件夹，读取所有的TXT文件并生成总结
def process_books_in_folder(folder_path):
    summaries = {}
    # 遍历文件夹中的所有文件
    for filename in os.listdir(folder_path):
        if filename.endswith('.txt'):  # 只处理txt文件
            file_path = os.path.join(folder_path, filename)
            print(f"Processing book: {filename}")
            content = read_txt(file_path)
            
            # 生成书籍总结
            summary = generate_book_summary(content)
            summaries[filename] = summary
    
    return summaries

# 使用示例
folder_path = 'output_book'  # 替换为你的文件夹路径
summaries = process_books_in_folder(folder_path)

# 输出每本书籍的总结
for book, summary in summaries.items():
    print(f"Summary for {book}:\n")
    print(summary)
    print("\n" + "="*50 + "\n")
