FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 kozos
COPY --chown=kozos:kozos . .
COPY --from=frontend --chown=kozos:kozos /frontend/dist ./frontend/dist
RUN mkdir -p /app/media /app/staticfiles && chown -R kozos:kozos /app/media /app/staticfiles
USER kozos
EXPOSE 8000
ENTRYPOINT ["sh", "/app/deploy/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--no-control-socket", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "60", "--access-logfile", "-", "--access-logformat", "%(m)s %(U)s %(s)s"]
