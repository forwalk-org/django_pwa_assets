#!/bin/bash

# """
# Tox-in-Docker Test Runner
#
# This script executes 'tox' inside a multi-python container.
# It uses the Dockerfile located in tests/docker/.
# """

IMAGE_NAME="django-pwa-assets-test"
USER_ID=$(id -u)
GROUP_ID=$(id -g)

# 1. Get the project root directory (one level up from this script)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 2. Build the custom image using the new path for Dockerfile.test
if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo "--- Building custom test image $IMAGE_NAME ---"
    docker build -t "$IMAGE_NAME" -f "$PROJECT_ROOT/tests/docker/Dockerfile.test" "$PROJECT_ROOT"
fi

echo "--- Starting Tox inside $IMAGE_NAME ---"

mkdir -p "$PROJECT_ROOT/.tox_docker"

# 3. Run tox
# Added a dedicated volume for .tox_docker to persist environments between runs
docker run --rm \
    --entrypoint "" \
    -v "$PROJECT_ROOT":/src \
    -v "$PROJECT_ROOT/.tox_docker":/src/.tox \
    -w /src \
    -u "${USER_ID}:${GROUP_ID}" \
    -e HOME=/tmp \
    "$IMAGE_NAME" tox "$@"

echo "--- Testing complete ---"
