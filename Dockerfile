FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ytfeed/ ytfeed/
COPY prompts/ prompts/

VOLUME /data
EXPOSE 8091
ENV YTFEED_CONFIG=/data/config.yml YTFEED_DATA=/data

HEALTHCHECK --interval=60s --timeout=5s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('YTFEED_PORT','8091')+'/healthz', timeout=4)"

CMD ["python", "-m", "ytfeed.main"]
