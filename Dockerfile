# Playwright 官方 Python 映像（已有 Chromium＋系統依賴）
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 報告字體（同 Jlaw-report 一樣用 @fontsource/noto-sans-tc 5.3.1）
RUN mkdir -p gen/node_modules/@fontsource && python3 -c "import urllib.request,tarfile,io;tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen('https://registry.npmjs.org/@fontsource/noto-sans-tc/-/noto-sans-tc-5.3.1.tgz').read())).extractall('gen/node_modules/@fontsource')" \
 && mv gen/node_modules/@fontsource/package gen/node_modules/@fontsource/noto-sans-tc
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python3", "app/server.py"]
