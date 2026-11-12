# Docker Setup for MiniRAG Application

This directory contains the Docker setup for the MiniRAG application, including all necessary services for development and monitoring.

## Services

- **FastAPI Application**: Main application running on Uvicorn
- **RabbitMQ**: Internal message broker for background jobs
- **Celery Worker**: Processes queued background jobs
- **Flower**: Authenticated Celery monitoring dashboard
- **Nginx**: Web server for serving the FastAPI application
- **PostgreSQL (pgvector)**: Vector-enabled database for storing embeddings
- **Postgres-Exporter**: Exports PostgreSQL metrics for Prometheus
- **Qdrant**: Vector database for similarity search
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboard for metrics
- **Node-Exporter**: System metrics collection

## Setup Instructions

### 1. Set up environment files

Run these commands from the repository root in PowerShell:

```powershell
Copy-Item docker\RAG\env\.env.app.example docker\RAG\env\.env.app
Copy-Item docker\RAG\env\.env.postgres.example docker\RAG\env\.env.postgres
Copy-Item docker\RAG\env\.env.postgres-exporter.example docker\RAG\env\.env.postgres-exporter
Copy-Item docker\RAG\env\.env.grafana.example docker\RAG\env\.env.grafana
Copy-Item docker\RAG\env\.env.rabbitmq.example docker\RAG\env\.env.rabbitmq
Copy-Item docker\RAG\env\.env.flower.example docker\RAG\env\.env.flower
```

Edit the generated files and replace example passwords and API keys. These
local `.env` files are ignored by Git; do not commit credentials.

### 2. Start the services

From the repository root:

```powershell
docker compose -f docker\docker-compose.yml up --build -d
```

RabbitMQ is available to other Compose services at `rabbitmq:5672`. Its AMQP
port is not published to the host. Set `RABBITMQ_DEFAULT_USER` and
`RABBITMQ_DEFAULT_PASS` in `docker/RAG/env/.env.rabbitmq` before starting the
stack. Keep this local file out of Git; RabbitMQ data is persisted in the
`rabbitmq_data` volume.

The `celery-worker` service uses the same `/app/data` volume as FastAPI so it
can access uploaded files. FastAPI, the worker, and Flower run as the
unprivileged `app` user (UID 10001). Before either FastAPI or the worker
starts, `data-volume-init` updates ownership of existing volume contents
once, preserving uploaded files. Flower is available at
`http://localhost:5555`, protected by the credentials in
`docker/RAG/env/.env.flower`. Replace the example Flower password before
starting the stack; the dashboard is only published on the local machine.

### 3. Understand non-root users and upload-volume ownership

FastAPI, the Celery worker, and Flower use the `app` account (UID/GID 10001)
from the shared application image. The worker and FastAPI share the
`fastapi_data` Docker volume at `/app/data`, so the worker can read files
uploaded by the API without running as root.

The volume may already contain files created by older root-running containers.
Before FastAPI or the worker starts, Compose runs `data-volume-init` as root
inside a short-lived container. It changes the volume contents' ownership to
UID/GID 10001 and then creates `/app/data/.ownership-initialized`. Compose
waits for that initializer to exit successfully. On subsequent starts, the
marker makes it skip the recursive ownership change. The initializer does not
delete uploads. Flower does not mount this volume.

The root user is used only for this one-time volume ownership setup; the API,
worker, and Flower processes remain non-root. This avoids granting the worker
root privileges while keeping existing uploaded files accessible.

#### Verify the normal startup

```powershell
docker compose -f docker\docker-compose.yml ps -a data-volume-init

docker inspect simple-rag-fastapi-1 simple-rag-celery-worker-1 simple-rag-flower-1 `
  --format '{{.Name}} user={{.Config.User}} state={{.State.Status}}'

docker compose -f docker\docker-compose.yml exec -T celery-worker sh -c `
  'id; test -w /app/data/uploaded_files && echo upload-volume-writable'

docker compose -f docker\docker-compose.yml exec -T celery-worker `
  celery -A src.infrastructure.celery.app:celery_app inspect ping

curl.exe -i http://127.0.0.1/health
```

Expected: `data-volume-init` exits with code 0; FastAPI, the worker, and
Flower report `user=app:app`; the upload volume is writable; the worker responds
with `pong`; and the health endpoint returns HTTP 200.

#### Repair volume permissions if needed

Only run this repair if the app user cannot access files. Stop services that
write to the shared volume first. The command changes ownership; it does not
remove files.

```powershell
docker compose -f docker\docker-compose.yml stop fastapi celery-worker flower nginx

docker compose -f docker\docker-compose.yml run --rm --no-deps `
  --user 0:0 --entrypoint /bin/sh data-volume-init `
  -c 'chown -R 10001:10001 /app/data'

docker compose -f docker\docker-compose.yml up -d fastapi celery-worker flower nginx
```

> Avoid `docker compose down -v` unless you intend to delete **all** Compose
> volumes, including uploaded files, the database, and RabbitMQ data.

### 4. Access the services

- FastAPI Application: http://localhost:8000
- FastAPI Documentation: http://localhost:8000/docs
- Nginx (serving FastAPI): http://localhost
- Flower: http://localhost:5555
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Qdrant UI: http://localhost:6333/dashboard

## Volume Management

### Managing Docker Volumes

Docker volumes are used to persist data generated by and used by Docker containers. Here are some commands to manage your volumes:

1. **List all volumes**:
   ```bash
   docker volume ls
   ```
2. **Inspect a volume**:
   ```bash
   docker volume inspect <volume_name>
   ```

   - list files in a volume:
   ```bash
   docker run --rm -v <volume_name>:/data busybox ls -l /data
   ```

3. **Remove a volume**:
   ```bash
   docker volume rm <volume_name>
   ```
4. **Prune unused volumes**:
   ```bash
    docker volume prune
    ```

5. **Backup volume for migration**:
   ```bash
    docker run --rm -v <volume_name>:/volume -v $(pwd):/backup alpine tar cvf /backup/backup.tar /volume
    ```

6. **Restore volume from backup**:
   ```bash
    docker run --rm -v <volume_name>:/volume -v $(pwd):/backup alpine sh -c "cd /volume && tar xvf /backup/backup.tar --strip 1"
    ```

7. **Remove all volumes**:
    ```bash
    docker volume rm $(docker volume ls -q)
    ```

**NOTE**: For PostgreSQL specifically, you might want to consider using PostgreSQL's built-in tools like `pg_dump` and `pg_restore` for more reliable backups, especially for live databases.

## Monitoring

### FastAPI Metrics

FastAPI is configured to expose Prometheus metrics at the `/metrics` endpoint. These metrics include:

- Request counts
- Request latencies
- Status codes

Prometheus is configured to scrape these metrics automatically.

### Visualizing Metrics in Grafana

1. Log into Grafana at http://localhost:3000 (default credentials: admin/admin_password)
2. Add Prometheus as a data source (URL: http://prometheus:9090)
3. Import dashboards for FastAPI, PostgreSQL, and Qdrant

#### Dashboards URLs

https://grafana.com/grafana/dashboards/18739-fastapi-observability/

https://grafana.com/grafana/dashboards/1860-node-exporter-full/

https://grafana.com/grafana/dashboards/23033-qdrant/

https://grafana.com/grafana/dashboards/12485-postgresql-exporter/


## Development Workflow

The FastAPI application is configured with hot-reloading. Any changes to the code in the `src/` directory will automatically reload the application.

## Troubleshooting

### Connection Errors

If you see connection errors when starting the services:

1. **Database Connection Refused**: This often happens when the FastAPI app tries to connect to databases before they're ready.
   ```
   Connection refused: [Errno 111] Connection refused
   ```
   
   Solutions:
   - Start database services first, wait, then start the application
   - Check database logs: `docker compose logs pgvector`
   - Ensure your database credentials in `.env.app` match those in `.env.postgres`

2. **Restart the FastAPI service** after databases are running:
   ```bash
   docker compose restart fastapi
   ```

3. **Check service status**:
   ```bash
   docker compose ps
   ```

4. **View logs** for more details:
   ```bash
   docker compose logs --tail=100 fastapi
   docker compose logs --tail=100 pgvector
   ```