# Engage Eight API. Build from the repo root (the API imports ../ml):
#   docker build -f api/Dockerfile -t engage-eight-api .
FROM python:3.12-slim

# libgomp: OpenMP runtime LightGBM needs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

# The ml package and the committed model; the training data is not needed.
COPY ml/engage8 ml/engage8
COPY ml/models ml/models
COPY api api

RUN useradd --system --uid 10001 engage8 && chown -R engage8 /srv
USER engage8
WORKDIR /srv/api

EXPOSE 8000
# Migrations run on startup (alembic upgrade head). Fails to start unless
# ENGAGE8_JWT_SECRET is set (ENGAGE8_DEBUG defaults to false).
# --no-proxy-headers: uvicorn would otherwise take the client IP from the first
# X-Forwarded-For entry, which the client controls. Rate limits read
# ENGAGE8_CLIENT_IP_HEADER instead (see render.yaml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
