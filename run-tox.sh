#!/bin/bash

# """
# Tox-in-Docker Test Runner (Debian Optimized)
#
# This script executes 'tox' inside the 'divio/multi-python' container.
# It bypasses the default entrypoint to avoid permission errors (chown)
# and runs directly as the current host user.
#
# Usage:
#   ./run-tox.sh
# """

IMAGE_NAME="django-pwa-assets-test"
USER_ID=$(id -u)
GROUP_ID=$(id -g)

# Build the custom image if it doesn't exist
if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo "--- Building custom test image $IMAGE_NAME ---"
    docker build -t "$IMAGE_NAME" -f Dockerfile.test .
fi

echo "--- Starting Tox inside $IMAGE_NAME ---"

# --entrypoint "": Overrides the image's script that causes the 'chown' error
# -v "$(pwd)":/src: Mounts your code to a neutral directory
# -w /src: Sets the working directory
# -e HOME=/tmp: Provides a writable home for Python/Tox cache
docker run --rm \
    --entrypoint "" \
    -v "$(pwd)":/src \
    -w /src \
    -u "${USER_ID}:${GROUP_ID}" \
    -e HOME=/tmp \
    "$IMAGE_NAME" tox "$@"

echo "--- Testing complete ---"
