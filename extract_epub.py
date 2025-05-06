from ebooklib import epub
from bs4 import BeautifulSoup
import ebooklib
import os

def extract_epub(epub_path):
   # 加载epub文件
   book = epub.read_epub(epub_path)
   all_text = []
   # 筛选正文的html章节
   for item in book.get_items():
      if item.get_type() == ebooklib.ITEM_DOCUMENT:
         # 使用BeautifulSoup清洗html得到纯文本
         soup = BeautifulSoup(item.get_content(),'lxml')
         text = soup.get_text()
         all_text.append(text)
   return '\n'.join(all_text)

def convert_epub(input_folder,output_folder):
   if not os.path.exists(output_folder):
      os.makedirs(output_folder)

   for file_name in os.listdir(input_folder):
      if file_name.endswith('.epub'):
         epub_path = os.path.join(input_folder,file_name)
         print(f'正在处理： {file_name}...')

         text = extract_epub(epub_path)

         output_file_name = file_name.replace('.epub','.txt')
         output_path = os.path.join(output_folder,output_file_name)

         with open(output_path,'w',encoding='utf-8') as f:
            f.write(text)
      print(f'处理完成： {file_name}')

input_folder = 'input_book'
output_folder = 'output_book'

convert_epub(input_folder,output_folder)