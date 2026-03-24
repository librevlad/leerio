FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl gosu unzip && rm -rf /var/lib/apt/lists/*

# Install deno (required by yt-dlp for YouTube JS challenge solving)
RUN curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

WORKDIR /app

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY server/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -r -s /usr/sbin/nologin appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
