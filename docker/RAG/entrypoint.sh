#!/bin/sh
set -eu

cd /app
alembic -c /app/docker/RAG/alembic.ini upgrade head
exec "$@"