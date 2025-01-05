# Variables
SHELL := /bin/bash
PROJECT := wmata-rail-position
VERSION := 0.1.0
IMAGE_NAME := wmata-rail-positions-python
COMPOSE_FILE := compose.yml
GIT_HASH := $(shell git log --format="%h" -n 1)
VENV := .venv
UV_PYTHON := uv run python
UV_PIP := uv pip
UV_PIP_SYNC := uv pip sync
UV_PIP_COMPILE := uv pip compile
UV_SYNC := uv sync
DOCKER_COMPOSE := docker compose -f $(COMPOSE_FILE) -p $(PROJECT)

# Colors
GREEN := $(shell tput setaf 2)
CYAN := $(shell tput setaf 6)
RESET := $(shell tput sgr0)

# Directories
TEST_DIR := ./tests
SRC_DIR := ./

# Default Target
.DEFAULT_GOAL := help

.PHONY: help
help: ## Display help information about available rules
	@echo "$(GREEN)Available rules:$(RESET)"
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | \
	awk -v cyan="$(CYAN)" -v reset="$(RESET)" 'BEGIN {FS = ":.*##"}; {printf "%s%-25s%s %s\n", cyan, $$1, reset, $$2}'


.PHONY: check-require
check-require: ## Verify required tools are installed
	@echo "Checking required tools..."
	@uv run python --version >/dev/null || (echo "ERROR: uv Python not found!" && exit 1)
	@uv --version >/dev/null || (echo "ERROR: uv is required!" && exit 1)
	@uvx --version >/dev/null || (echo "ERROR: uvx is required!" && exit 1)
	@uvx ruff --version >/dev/null || (echo "ERROR: ruff is required!" && exit 1)
	@echo "All required tools are installed."

.PHONY: init
init: check-require ## Initialize virtual environment using uv
	@if [ ! -d $(VENV) ]; then \
		echo "Creating virtual environment with uv..."; \
		uv venv $(VENV); \
	fi
	@$(MAKE) sync
	@echo "Virtual environment initialized."

.PHONY: sync
sync: ## Synchronize Python dependencies
	@echo "Synchronizing Python dependencies with uv sync..."
	@$(UV_SYNC)

.PHONY: test
test: ## Run tests with pytest
	@echo "Running tests..."
	@$(UV_PYTHON) -m pytest $(TEST_DIR)

.PHONY: lint
lint: ## Run linting with ruff
	@echo "Linting code..."
	@uvx ruff check

.PHONY: format
format: ## Format code with ruff
	@echo "Formatting code..."
	@uvx ruff format

.PHONY: build
build: init ## Build the Docker image
	@echo "Building Docker image..."
	@docker build -t $(IMAGE_NAME) -f Dockerfile $(SRC_DIR) 

.PHONY: run
run: ## Run the application locally
	@echo "Running application..."
	@$(UV_PYTHON) main.py

.PHONY: up
up: ## Start Docker Compose services
	@echo "Starting Docker Compose services..."
	@$(DOCKER_COMPOSE) up -d

.PHONY: start
start: ## Start Docker Compose services without recreating containers
	@echo "Starting existing Docker Compose services..."
	@$(DOCKER_COMPOSE) start

.PHONY: stop
stop: ## Stop Docker Compose services without removing containers
	@echo "Stopping Docker Compose services..."
	@$(DOCKER_COMPOSE) stop

.PHONY: down
down: ## Stop and remove Docker Compose services
	@echo "Stopping and removing Docker Compose services..."
	@$(DOCKER_COMPOSE) down

.PHONY: clean
clean: ## Clean up virtual environment and other generated files
	@echo "Cleaning up environment..."
	@if [ -d $(VENV) ]; then \
		echo "Removing virtual environment..."; \
		rm -rf $(VENV); \
	fi
	@find . -type d -name '__pycache__' -exec rm -rf {} +
	@find . -type f -name '*.pyc' -delete
	@find . -type f -name '*.pyo' -delete
	@find . -type f -name '*.log' -delete
	@find . -type f -name '*.egg-info' -exec rm -rf {} +
	@find . -type f -name '*.dist-info' -exec rm -rf {} +
	@echo "Clean-up complete."

.PHONY: create-k8s-deployment
create-k8s-deployment: ## Create Kubernetes deployment
	@echo "Creating Kubernetes deployment..."
	@$(UV_PYTHON) annotate-elastic-apm.py -m "Created application deployment"
	# kubectl apply -f wmata_rail_position_deployment.yaml

.PHONY: delete-k8s-deployment
delete-k8s-deployment: ## Delete Kubernetes deployment
	@echo "Deleting Kubernetes deployment..."
	@$(UV_PYTHON) annotate-elastic-apm.py -m "Deleted application deployment"
	# kubectl delete -f wmata_rail_position_deployment.yaml
