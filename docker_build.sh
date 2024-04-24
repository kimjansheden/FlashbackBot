#!/bin/bash

# Check if the model path argument is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <model_path>"
    exit 1
fi

# Use the first argument as the model source path
MODEL_DIR="$1"

# Specify the temporary directory within your Docker build context
TEMP_MODEL_PATH="./temp_model"

# Create the temporary directory and copy the model there
mkdir -p "${TEMP_MODEL_PATH}" && cp -R "${MODEL_DIR}/." "${TEMP_MODEL_PATH}/"

# Build the Docker image
docker build --build-arg MODEL_DIR="${MODEL_DIR}" -t fbbot .

# Check if Docker build was successful
if [ $? -eq 0 ]; then
    echo "Docker image successfully built. Deleting temporary model directory..."
    # Delete the temporary directory if Docker build was successful
    rm -rf "${TEMP_MODEL_PATH}"
else
    echo "Docker build failed. Keeping temporary model directory for troubleshooting."
fi
