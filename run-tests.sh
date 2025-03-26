#!/bin/bash
echo "Running tests in Docker container"
echo "Tests will be run against a PostgreSQL database in a Docker container"
echo "Test database: backend_test"

COMPOSE_BAKE=false docker-compose -f docker-compose.test.yml up --build
