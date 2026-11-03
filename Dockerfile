FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk espeak-ng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000
# 進捗をメモリで持つため worker は1つ
CMD gunicorn -b 0.0.0.0:$PORT -w 1 --threads 8 --timeout 900 app:app
