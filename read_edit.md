# 本地运行说明

## 前置配置

### KEY配置
    在项目根目录下创建.env文件，写入以下内容：
TAVILY_API_KEY=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
OPENAI_API_KEY=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

### ui配置
    在ui文件夹内创建.env文件，写入以下内容：    
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## 前端
```
npm install
cd ui 
npm run dev
```

## 启动项目
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python application.py
```
