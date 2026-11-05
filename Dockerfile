# 行動卡解析（signals.js＋pdfjs-dist 4.10，要 Node ≥20）：用官方 Node 22 裝好，再複製去主映像
FROM node:22-slim AS sig
WORKDIR /sig
COPY gen/sig/package.json gen/sig/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

# Playwright 官方 Python 映像（已有 Chromium＋系統依賴）
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils fonts-noto-cjk imagemagick && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 報告字體（同 Jlaw-report 一樣用 @fontsource/noto-sans-tc 5.3.1）
RUN mkdir -p gen/node_modules/@fontsource && python3 -c "import urllib.request,tarfile,io;tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen('https://registry.npmjs.org/@fontsource/noto-sans-tc/-/noto-sans-tc-5.3.1.tgz').read())).extractall('gen/node_modules/@fontsource')" \
 && mv gen/node_modules/@fontsource/package gen/node_modules/@fontsource/noto-sans-tc
COPY . .
COPY --from=sig /usr/local/bin/node /usr/local/bin/node
COPY --from=sig /sig/node_modules gen/sig/node_modules
ENV PYTHONUNBUFFERED=1
CMD ["python3", "app/server.py"]
