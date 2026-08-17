FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
ENV SUBTITLE_FONT_PATH=/srv/app/assets/fonts/Prompt-Bold.ttf
ARG PROMPT_FONT_URL=https://raw.githubusercontent.com/google/fonts/main/ofl/prompt/Prompt-Bold.ttf
ARG PROMPT_FONT_SHA256=02813ca4f93c1df27e271f10fef3db6e34e66751ae1f4a3ed82ae06cb20150ea
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl libraqm0 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /srv/app/assets/fonts \
    && curl --fail --location --retry 3 --retry-all-errors \
        "$PROMPT_FONT_URL" --output "$SUBTITLE_FONT_PATH" \
    && echo "$PROMPT_FONT_SHA256  $SUBTITLE_FONT_PATH" | sha256sum --check --strict
WORKDIR /srv/app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app app
RUN mkdir -p /data/jobs /data/beat
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
