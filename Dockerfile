FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY storage_expert/ ./storage_expert/
COPY web/ ./web/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]
