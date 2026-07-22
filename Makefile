# GridCast — common commands. Run `make help` for the list.

.PHONY: help install install-dbt ingest-dry ingest api dashboard dbt-build test lint

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## Install app deps (ingest/ml/serve/dev) + local package
	pip install -e . -r requirements/ml.txt -r requirements/serve.txt \
		-r requirements/monitoring.txt -r requirements/dev.txt

install-dbt:  ## Install dbt-snowflake (do this in a separate venv)
	pip install -r requirements/dbt.txt

ingest-dry:  ## D1 — dry-run ingestion (no AWS), lands nothing
	python -m src.ingestion.run --dry-run

ingest:  ## D1 — real ingestion to S3
	python -m src.ingestion.run

dbt-build:  ## D2/D3 — run staging + marts (from dbt/gridcast)
	cd dbt/gridcast && dbt deps && dbt build --profiles-dir .

api:  ## D5 — serve FastAPI at :8000
	uvicorn src.api.main:app --reload --port 8000

dashboard:  ## D6 — serve Streamlit at :8501
	streamlit run src/dashboard/app.py

test:  ## run pytest
	pytest -q

lint:  ## run ruff
	ruff check src tests

tf-init:  ## D10 — init the terraform working dir (ECR + GitHub OIDC role)
	cd terraform && terraform init

tf-plan:  ## D10 — show what terraform would change
	cd terraform && terraform plan

tf-apply:  ## D10 — create/update the ECR repos + GitHub Actions IAM role
	cd terraform && terraform apply
