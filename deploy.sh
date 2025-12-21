#!/bin/bash

# Navigate to the project directory
cd /path/to/your/project

# Pull the latest changes from the repository
git pull origin main

# Rebuild and restart the container
docker-compose up -d --build
