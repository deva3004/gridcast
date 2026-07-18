FROM python:3.11-slim

WORKDIR /app

# LightGBM's Linux wheel dynamically links libgomp at runtime; the slim
# base image doesn't ship it, so `import lightgbm` fails without this.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/serve.txt requirements/
RUN pip install --no-cache-dir -r requirements/serve.txt

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

EXPOSE 8000
