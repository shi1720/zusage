# ---------------------------------------------------------------------------
# Zusage — single-container build.
# Stage 1 compiles the React app; stage 2 is a slim Python runtime serving the
# API and the static bundle. Fonts are bundled: the image runs air-gapped.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /build
COPY src/frontend/package.json src/frontend/package-lock.json src/frontend/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY src/frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ZUSAGE_DATA_DIR=/app/data \
    ZUSAGE_STATIC_DIR=/app/static \
    ZUSAGE_DATABASE_URL=sqlite:////app/var/zusage.db
WORKDIR /app
COPY src/backend/pyproject.toml /app/backend/pyproject.toml
COPY src/backend/zusage /app/backend/zusage
RUN pip install --no-cache-dir /app/backend && rm -rf /root/.cache
COPY data/ /app/data/
COPY --from=web /build/dist /app/static
RUN useradd --create-home --uid 10001 zusage && mkdir -p /app/var && chown zusage /app/var
USER zusage
VOLUME ["/app/var"]
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health').status==200 else 1)"
CMD ["uvicorn", "zusage.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
