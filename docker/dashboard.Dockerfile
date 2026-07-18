FROM python:3.11-slim

WORKDIR /app

COPY requirements/base.txt requirements/serve.txt requirements/
RUN pip install --no-cache-dir -r requirements/serve.txt

COPY pyproject.toml .
COPY src/ src/
COPY config/ config/
RUN pip install --no-cache-dir -e .

EXPOSE 8501
