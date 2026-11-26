# Stage 1: install Python dependencies (build tools do not enter runtime).
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt ./
RUN python -m pip install --prefix=/install -r requirements.txt

# Stage 2: minimal runtime; never run the app as root.
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app

COPY --from=builder /install /usr/local
RUN groupadd --system agent && useradd --system --gid agent --home-dir /app agent
COPY --chown=agent:agent app/ ./app/
COPY --chown=agent:agent utils/ ./utils/

USER agent
EXPOSE 8000

# Health check stays independent of Redis: the process can be live even if unready.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT','8000') + '/health', timeout=2)" || exit 1

# Shell only expands PORT; exec replaces shell so uvicorn receives SIGTERM as PID 1.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
