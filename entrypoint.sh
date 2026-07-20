#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Seeding source configs..."
python -m scripts.seed_sources

echo "Seeding Neo4j graph nodes..."
i=1
while [ "$i" -le 5 ]; do
  if python -m scripts.seed_graph; then
    break
  fi
  echo "seed_graph attempt $i failed; retrying in 5s..."
  i=$((i + 1))
  sleep 5
done

exec "$@"
