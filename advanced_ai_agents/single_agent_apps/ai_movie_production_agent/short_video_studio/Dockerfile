# Container used to run Short Video Studio on a Hugging Face Space.
FROM python:3.12-slim

# Fonts for the video headlines and subtitles.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && (apt-get install -y --no-install-recommends fonts-inter || true) \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face runs Spaces as user 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    OUTPUT_MAX_AGE_HOURS=24
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
