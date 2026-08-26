#!/bin/bash
# Rendered by Terraform's templatefile() in compute.tf -- every
# placeholder below is substituted at plan/apply time, not left for bash
# to expand.
set -euxo pipefail

dnf update -y
dnf install -y docker
systemctl enable --now docker

# AL2023 doesn't ship the compose plugin by default; install it the way
# Docker's own docs recommend for a plugin-less base image.
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/gridcast/data/cache /opt/gridcast/data/model
cd /opt/gridcast

aws ecr get-login-password --region ${aws_region} \
  | docker login --username AWS --password-stdin ${account_id}.dkr.ecr.${aws_region}.amazonaws.com

# SNOWFLAKE_* creds for refresh_feature_cache.py -- created out-of-band,
# never committed. See problem_faced.txt entry 13 for why Terraform itself
# doesn't own this value. Currently a placeholder: the source warehouse is
# unreachable, so this only satisfies the parameter's existence for the
# get-parameter call below (set -e would otherwise kill the whole script) --
# the API itself never reads Snowflake creds, only the hourly refresh cron
# does, and that's expected to fail harmlessly until the warehouse is back.
aws ssm get-parameter \
  --region ${aws_region} \
  --name "${ssm_param_name}" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text > /opt/gridcast/.env

# Pretrained model + last-known feature snapshot, uploaded out-of-band to S3
# (see terraform/iam_ec2.tf's app_instance_s3_read policy). Stand-ins for a
# fresh train + a fresh warehouse pull, neither of which is possible right
# now -- both land under ./data, which the api container mounts as /app/data.
aws s3 cp "s3://${artifacts_bucket}/${artifacts_prefix}/model_lightgbm.pkl" \
  /opt/gridcast/data/model/model_lightgbm.pkl
aws s3 cp "s3://${artifacts_bucket}/${artifacts_prefix}/latest_features.csv" \
  /opt/gridcast/data/cache/latest_features.csv

cat > /opt/gridcast/docker-compose.yml <<COMPOSE
services:
  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.16.2
    command: >
      mlflow server --host 0.0.0.0 --port 5000
      --backend-store-uri sqlite:////mlflow/mlflow.db
      --artifacts-destination /mlflow/artifacts
    volumes: ["mlflow_data:/mlflow"]
    restart: unless-stopped
    logging:
      driver: awslogs
      options:
        awslogs-region: "${aws_region}"
        awslogs-group: "${log_group_name}"
        awslogs-stream: mlflow

  api:
    image: ${api_image}
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
    env_file: [.env]
    environment:
      MLFLOW_TRACKING_URI: "http://mlflow:5000"
    volumes: ["./data:/app/data"]
    ports: ["8000:8000"]
    depends_on: [mlflow]
    restart: unless-stopped
    logging:
      driver: awslogs
      options:
        awslogs-region: "${aws_region}"
        awslogs-group: "${log_group_name}"
        awslogs-stream: api

  dashboard:
    image: ${dashboard_image}
    command: streamlit run src/dashboard/app.py --server.address 0.0.0.0
    environment:
      GRIDCAST_API_URL: "http://api:8000"
    ports: ["8501:8501"]
    depends_on: [api]
    restart: unless-stopped
    logging:
      driver: awslogs
      options:
        awslogs-region: "${aws_region}"
        awslogs-group: "${log_group_name}"
        awslogs-stream: dashboard

volumes:
  mlflow_data:
COMPOSE

# Bring mlflow up first and wait for it before starting api -- api resolves
# the @production alias once at process startup (src/api/main.py), and a
# freshly-booted instance's registry is empty (ephemeral by design, see
# compute.tf's health_check_type comment) until the register step below runs.
docker compose up -d mlflow
until curl -sf http://localhost:5000/version >/dev/null; do sleep 2; done

# Import the already-trained model into this instance's registry -- no
# retraining, the source warehouse is unreachable right now anyway.
docker compose run --rm --no-deps api python -m src.api.register_pretrained_model

docker compose up -d

# First cache population attempt -- expected to fail harmlessly right now
# (Snowflake unreachable); the seeded latest_features.csv above is what
# /forecast actually serves from until the warehouse is back.
sleep 15
docker compose exec -T api python -m src.api.refresh_feature_cache || true

# Interim scheduler until Airflow DAGs replace it (deliberately last in
# this project's sequencing) -- refresh_feature_cache.py's own docstring
# calls for cron/Airflow, and there's no Airflow yet.
cat > /etc/cron.d/gridcast-refresh <<'CRON'
0 * * * * root cd /opt/gridcast && /usr/bin/docker compose exec -T api python -m src.api.refresh_feature_cache >> /var/log/gridcast-refresh.log 2>&1
CRON
chmod 644 /etc/cron.d/gridcast-refresh
