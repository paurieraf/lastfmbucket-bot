#!/bin/bash

# Pull the latest changes from the repository
git pull origin main

# Rebuild and restart the container
docker compose up -d --build
