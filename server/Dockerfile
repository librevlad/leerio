FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl gosu && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY server/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -r -s /usr/sbin/nologin appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
