# Variables
SHELL:=/bin/bash
PROJECT := wmata-rail-position
IMAGE_NAME := wmata-rail-position-python
COMPOSE_FILE := compose.yml
GIT_HASH ?= $(shell git log --format="%h" -n 1)
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PIP_COMPILE = $(VENV)/bin/pip-compile
PIP_SYNC = $(VENV)/bin/pip-sync

# Assumes the use of pyenv for managing Python versions
PYENV_ROOT := $(HOME)/.pyenv
PATH := $(PYENV_ROOT)/shims:$(PYENV_ROOT)/bin:$(PATH)

# Define color variables
GREEN := $(shell tput setaf 2)
CYAN := $(shell tput setaf 6)
RESET := $(shell tput sgr0)

# Requirements files
REQUIREMENTS_IN = ./app/requirements/prod.in
REQUIREMENTS_TXT = ./app/requirements/prod.txt
DEV_REQUIREMENTS_IN = ./app/requirements/dev.in
DEV_REQUIREMENTS_TXT = ./app/requirements/dev.txt

# Directories
TEST_DIR = tests
SRC_DIR = ./app

# Commands for testing and linting
TEST_CMD = ./$(VENV)/bin/pytest $(TEST_DIR)
LINT_CMD = ./$(VENV)/bin/flake8 --exclude $(VENV) $(SRC_DIR)
FMT_CMD = ./$(VENV)/bin/black $(SRC_DIR)

PYTHON_CMD := $(shell command -v python || command -v python3)

# If python is not found, print an error message and exit
ifeq ($(PYTHON_CMD),)
  $(error "Python is required but not found.")
endif

# Get Python version
PYTHON_VERSION := $(shell $(PYTHON_CMD) --version 2>&1 | cut -d' ' -f2)

# Split Python version into major, minor, and patch components
PYTHON_MAJOR_VERSION := $(shell echo $(PYTHON_VERSION) | cut -d. -f1)
PYTHON_MINOR_VERSION := $(shell echo $(PYTHON_VERSION) | cut -d. -f2)
PYTHON_PATCH_VERSION := $(shell echo $(PYTHON_VERSION) | cut -d. -f3)

# Check if Python minor version is >= 11
ifeq ($(shell [ $(PYTHON_MINOR_VERSION) -ge 11 ] && echo 1 || echo 0), 0)
  $(error "Python version must be 3.11 or higher. Detected: $(PYTHON_VERSION)")
endif

.DEFAULT_GOAL := help

.PHONY: help
help: ## Display help information about available rules
	@echo "$(GREEN)Available rules:$(RESET)"
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | \
	awk -v cyan="$(CYAN)" -v reset="$(RESET)" 'BEGIN {FS = ":.*##"}; {printf "- %s%s%s\n    %s\n\n", cyan, $$1, reset, $$2}'

.PHONY: check-python-version
check-python-version: ## Check the Python version
	@echo "Using Python: $(PYTHON)"
	@echo "Python Version: $(PYTHON_VERSION)"

all: init compile-requirements sync-requirements ## Setup environment and install dependencies
	@echo "Running target: all"

init: check-python-version ## Create a virtual environment
	@echo "Running target: init"
	@if [ ! -d $(VENV) ]; then \
		echo "Virtual environment does not exist, creating new virtual environment ..."; \
		$(PYTHON_CMD) -m venv $(VENV); \
	fi

	@echo "Installing requirements into virtual environment..."
	@$(PIP) install --upgrade pip setuptools wheel pip-tools
	@$(MAKE) compile-requirements
	@$(MAKE) sync-requirements
	@echo "Virtual environment setup complete."

.PHONY: compile-requirements
compile-requirements: ## pip-compile Python requirement files
	@echo "Running target: compile-requirements"
	@$(PIP_COMPILE) $(REQUIREMENTS_IN) -o $(REQUIREMENTS_TXT)
	@$(PIP_COMPILE) $(DEV_REQUIREMENTS_IN) -o $(DEV_REQUIREMENTS_TXT)

.PHONY: sync-requirements
sync-requirements: ## pip-sync Python modules with virtual environment
	@echo "Running target: sync-requirements"
	@$(PIP_SYNC) $(DEV_REQUIREMENTS_TXT)

.PHONY: test
test: ## Run unit tests
	@echo "Running target: test"
	$(TEST_CMD)

.PHONY: lint
lint: ## Run linting to check code style
	@echo "Running target: lint"
	$(LINT_CMD)

.PHONY: fmt
fmt: ## Run linting to check code style
	@echo "Running target: fmt"
	$(FMT_CMD)

build: init ## Build the Docker image
	@echo "Running target: build"
	docker build -t $(IMAGE_NAME) ./app

.PHONY: up
up: ## Create and start the Docker Compose services
	@echo "Running target: up"
	docker compose -f $(COMPOSE_FILE) -p $(PROJECT) up -d

.PHONY: start
start: ## Start the Docker Compose services
	@echo "Running target: start"
	docker compose -f $(COMPOSE_FILE) -p $(PROJECT) start

.PHONY: stop
stop: ## Stop the Docker Compose services
	@echo "Running target: stop"
	docker compose -f $(COMPOSE_FILE) -p $(PROJECT) stop

.PHONY: down
down: ## Stop and remove the Docker Compose services
	@echo "Running target: down"
	docker compose -f $(COMPOSE_FILE) -p $(PROJECT) down

.PHONY: create-k8s-deployment
create-k8s-deployment: ## Create k8s deployment
	@echo "Running target: create-k8s-deployment"
	@source $(VENV)/bin/activate; \
	$(PYTHON) ./annotate_elastic_apm.py -m "Created application deployment"; \
	#kubectl apply -f wmata_rail_position_deployment.yaml

.PHONY: delete-k8s-deployment
delete-k8s-deployment: ## Delete k8s deployment
	@echo "Running target: delete-k8s-deployment"
	@source $(VENV)/bin/activate; \
	$(PYTHON) ./annotate_elastic_apm.py -m "Deleted application deployment"; \
	#kubectl delete -f wmata_rail_position_deployment.yaml

.PHONY: clean
clean: ## Clean up virtual environment and other generated files
	@echo "Running target: clean"
	@if [ -d $(VENV) ]; then \
		echo "Removing existing virtual environment ..."; \
		rm -rf $(VENV); \
	fi

	@find . -type d -name '__pycache__' -exec rm -r {} +
	@find . -type f -name '*.pyc' -exec rm -f {} +
	@find . -type f -name '*.pyo' -exec rm -f {} +
	@find . -type f -name '*.log' -exec rm -f {} +
	@find . -type f -name '*.egg-info' -exec rm -rf {} +
	@find . -type f -name '*.dist-info' -exec rm -rf {} +
