FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy app + data
COPY server.py .
COPY data/ data/

ENV PORT=8080
EXPOSE 8080

CMD python server.py
