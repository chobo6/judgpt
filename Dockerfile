FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY judgpt/ ./judgpt/
RUN pip install --no-cache-dir ".[web]"
COPY --from=frontend-build /frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "judgpt.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
