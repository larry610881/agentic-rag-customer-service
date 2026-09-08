FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "mcp==1.29.1" "uvicorn[standard]==0.34.0" "starlette>=0.46"

COPY main.py .

ENV PORT=8080
EXPOSE 8080
CMD ["python", "main.py"]
