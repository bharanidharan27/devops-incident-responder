# DevOps Incident Responder

Local-first incident triage product for DevOps/SRE workflows. It accepts manual or webhook incidents, collects related logs, retrieves local knowledge-base context, runs a provider-agnostic RCA analysis, and shows every step in Streamlit.

## What It Does

- Manual and webhook-style incident intake through FastAPI.
- Background worker that processes `OPEN` incidents end to end.
- Collector, analyst, and supervisor stages with persisted timeline rows.
- Local RAG by default using Chroma when installed, with a JSON vector fallback.
- Free-first AI adapter through LiteLLM: Gemini, Groq, Hugging Face, or Ollama can be swapped by `.env` only.
- Deterministic rule-based fallback when no AI provider is configured.
- Streamlit UI for incident creation, timeline, evidence, RCA reports, and provider status.

## Recommended Next Product Move

CloudWatch is the right next integration if the target customer is AWS-based SRE/DevOps teams. Keep it as a source adapter, not a hard dependency: the app should still support manual/webhook intake and local demo logs so it remains easy to evaluate without AWS credentials.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

python scripts/seed_logs.py
python scripts/seed_rag_examples.py
python scripts/seed_incidents.py

python -m app.runner --once
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
python -m streamlit run ui/streamlit_app.py --server.headless true
```

The app works without OpenAI credentials. If no free hosted or local provider is configured, the analyst uses the rule-based fallback and still produces a report.

On Windows PowerShell, the API command is expected to keep running. Wait for `Uvicorn running on http://127.0.0.1:8000`; press `Ctrl+C` only when you want to stop it.

## Docker

The repository builds one image that can run either the FastAPI server or the Streamlit UI. FastAPI owns database access and incident processing; Streamlit calls FastAPI through `API_BASE_URL`.

```bash
docker build -t devops-incident-responder .
docker network create incident-responder

docker run --rm --name incident-api --network incident-responder -p 8000:8000 `
  -e PORT=8000 `
  devops-incident-responder scripts/start_api.sh

docker run --rm --name incident-ui --network incident-responder -p 8501:8501 `
  -e API_BASE_URL=http://incident-api:8000 `
  devops-incident-responder scripts/start_streamlit.sh
```

For local Docker without `DATABASE_URL`, the API uses SQLite at `/data/dev.db`. For AWS, set `DATABASE_URL` to the RDS PostgreSQL URL.

## AWS ECS + RDS Deployment

The recommended AWS deployment is ECS Fargate with one task running two containers from the same ECR image:

- `api`: FastAPI on container port `8000`, command `scripts/start_api.sh`.
- `ui`: Streamlit on container port `8501`, command `scripts/start_streamlit.sh`.
- Application Load Balancer routes `/api/*`, `/health`, `/docs`, and `/openapi.json` to `api`; default traffic goes to `ui`.
- RDS PostgreSQL stores incidents, agent steps, and reports. Store the SQLAlchemy URL in Secrets Manager as `DATABASE_URL`.

Default values used below:

```powershell
$Region = "us-east-1"
$App = "devops-incident-responder"
$DbName = "incident_responder"
$AccountId = aws sts get-caller-identity --query Account --output text
```

### 1. Build and Push the Image

```powershell
aws ecr create-repository --repository-name $App --region $Region
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

docker build -t "${App}:latest" .
docker tag "${App}:latest" "$AccountId.dkr.ecr.$Region.amazonaws.com/${App}:latest"
docker push "$AccountId.dkr.ecr.$Region.amazonaws.com/${App}:latest"
```

### 2. Create RDS PostgreSQL and Store the Secret

Create a PostgreSQL RDS instance in the same VPC/subnets as ECS. The app expects a SQLAlchemy-compatible URL:

```text
postgresql+psycopg://<db-user>:<db-password>@<rds-endpoint>:5432/incident_responder
```

Store it in Secrets Manager:

```powershell
$DatabaseUrlSecretArn = aws secretsmanager create-secret `
  --name "$App/database-url" `
  --secret-string "postgresql+psycopg://<db-user>:<db-password>@<rds-endpoint>:5432/$DbName" `
  --query ARN `
  --output text `
  --region $Region
```

### 3. Register the ECS Task Definition

Copy `deploy/aws/ecs-task-definition.example.json`, replace `<account-id>`, `<database-url-secret-arn>`, and any region/image values, then register it:

```powershell
aws logs create-log-group --log-group-name "/ecs/$App" --region $Region
aws ecs register-task-definition --cli-input-json file://deploy/aws/ecs-task-definition.example.json --region $Region
```

The ECS task execution role must be able to pull from ECR, write CloudWatch Logs, and read the Secrets Manager secret.

### 4. Create ALB Target Groups and Listener Rules

Create two target groups with target type `ip`:

```powershell
$VpcId = "<vpc-id>"

$ApiTargetGroupArn = aws elbv2 create-target-group `
  --name "$App-api" `
  --protocol HTTP `
  --port 8000 `
  --vpc-id $VpcId `
  --target-type ip `
  --health-check-path /health `
  --query "TargetGroups[0].TargetGroupArn" `
  --output text `
  --region $Region

$UiTargetGroupArn = aws elbv2 create-target-group `
  --name "$App-ui" `
  --protocol HTTP `
  --port 8501 `
  --vpc-id $VpcId `
  --target-type ip `
  --health-check-path /_stcore/health `
  --query "TargetGroups[0].TargetGroupArn" `
  --output text `
  --region $Region
```

Create an internet-facing ALB and HTTP listener. Set the listener default action to `$UiTargetGroupArn`, then add an API rule:

```powershell
aws elbv2 create-rule `
  --listener-arn "<listener-arn>" `
  --priority 10 `
  --conditions Field=path-pattern,Values="/api/*","/health","/docs","/openapi.json" `
  --actions Type=forward,TargetGroupArn=$ApiTargetGroupArn `
  --region $Region
```

### 5. Create the ECS Service

Use private subnets when you have NAT, or public subnets with `assignPublicIp=ENABLED` for the first low-friction deployment. The RDS security group must allow inbound PostgreSQL `5432` from the ECS task security group.

```powershell
aws ecs create-cluster --cluster-name $App --region $Region

aws ecs create-service `
  --cluster $App `
  --service-name $App `
  --task-definition $App `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[<subnet-a>,<subnet-b>],securityGroups=[<ecs-security-group>],assignPublicIp=ENABLED}" `
  --load-balancers "targetGroupArn=$ApiTargetGroupArn,containerName=api,containerPort=8000" "targetGroupArn=$UiTargetGroupArn,containerName=ui,containerPort=8501" `
  --region $Region
```

When deployment stabilizes, open the ALB DNS name. The UI should load Streamlit, and `/health` should return the FastAPI health payload.

## API

- `POST /api/incidents`
- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `GET /api/incidents/{id}/steps`
- `GET /api/incidents/{id}/report`
- `POST /api/incidents/{id}/run`
- `POST /api/rag/reindex`
- `POST /api/webhooks/alertmanager`

Example incident:

```json
{
  "service": "payment-service",
  "environment": "prod",
  "severity": "CRITICAL",
  "title": "Checkout HTTP 500 spike",
  "description": "HTTP 500 errors increased on checkout",
  "alert_type": "HTTP 500",
  "source": "webhook",
  "external_id": "alert-123",
  "payload": {"region": "us-east-1"}
}
```

## Provider Switching

Set `LLM_MODEL` and `LLM_FALLBACK_MODELS` in `.env`.

```env
LLM_MODEL=gemini/gemini-2.5-flash-lite
LLM_FALLBACK_MODELS=groq/qwen/qwen3-32b,ollama/gemma3
GEMINI_API_KEY=
GROQ_API_KEY=
OLLAMA_ENABLED=false
```

No code changes are required to switch providers. Hosted logs are redacted before they are sent to an AI provider.

## CloudWatch Logs Setup

Local seeded logs are still the default. To read from AWS CloudWatch Logs, configure `.env`:

```env
LOGS_MODE=cloudwatch
AWS_REGION=us-east-1
AWS_PROFILE=your-profile
CLOUDWATCH_LOG_GROUPS=/aws/lambda/payment-service,/aws/ecs/checkout
CLOUDWATCH_LOOKBACK_MINUTES=30
CLOUDWATCH_MAX_EVENTS=100
CLOUDWATCH_FALLBACK_TO_LOCAL=true
```

The AWS identity needs read-only CloudWatch Logs permissions:

```json
{
  "Effect": "Allow",
  "Action": [
    "logs:FilterLogEvents",
    "logs:DescribeLogGroups",
    "logs:DescribeLogStreams"
  ],
  "Resource": "*"
}
```

Webhook incidents can override the default log group:

```json
{
  "service": "payment-service",
  "severity": "CRITICAL",
  "alert_type": "HTTP 500",
  "payload": {
    "cloudwatch_log_groups": ["/aws/lambda/payment-service"],
    "cloudwatch_filter_pattern": "ERROR",
    "cloudwatch_log_stream_prefix": "2026/05/16"
  }
}
```

If CloudWatch credentials or log groups are missing and `CLOUDWATCH_FALLBACK_TO_LOCAL=true`, the collector records a warning step and falls back to local sample logs.

## Simulate Alertmanager + CloudWatch End-to-End

Prometheus Alertmanager is open source and supports generic webhook receivers, which makes it the best free first integration path. PagerDuty can be added later as another webhook parser, but Alertmanager gives us a no-license route for real or simulated alerts.

1. Configure `.env`:

```env
LOGS_MODE=cloudwatch
AWS_PROFILE=default
AWS_REGION=us-east-1
CLOUDWATCH_LOG_GROUPS=/devops-incident-responder/payment-service
CLOUDWATCH_STREAM_PREFIX=demo
WEBHOOK_AUTO_PROCESS=true
```

2. Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

3. Rebuild the local RAG index so the demo runbooks are available:

```powershell
.\.venv\Scripts\python.exe -m app.rag.build_index
```

4. In another terminal, write demo logs into CloudWatch:

```powershell
.\.venv\Scripts\python.exe scripts/simulate_cloudwatch_logs.py --scenario http500 --log-group /devops-incident-responder/payment-service --stream-prefix demo
```

5. Send an Alertmanager-compatible webhook:

```powershell
.\.venv\Scripts\python.exe scripts/simulate_alertmanager_alert.py --scenario http500 --log-group /devops-incident-responder/payment-service --stream-prefix demo
```

The webhook creates the incident automatically. With `WEBHOOK_AUTO_PROCESS=true`, the API immediately runs the collector/analyst/supervisor flow, retrieves matching CloudWatch events, and writes the report.

For a faster demo, omit `--scenario` to pick randomly:

```powershell
.\.venv\Scripts\python.exe scripts/simulate_cloudwatch_logs.py --log-group /devops-incident-responder/payment-service --stream-prefix demo
.\.venv\Scripts\python.exe scripts/simulate_alertmanager_alert.py --log-group /devops-incident-responder/payment-service --stream-prefix demo
```

The CloudWatch simulator writes the selected scenario to `.demo_scenario`, and the Alertmanager simulator reads that file by default, so the two commands still match even when the scenario is random.

Scenario options:

- `http500`
- `db`
- `oom`
- `latency`
- `auth`
- `queue`

CloudWatch ingestion may create small AWS charges. The simulator sets a short retention policy by default using `CLOUDWATCH_SIMULATION_RETENTION_DAYS=1`.
