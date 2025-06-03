.PHONY: init test clean build-image init-minikube dev-webapp dev-webapp-ts clean-webapp help

PIPX := $(shell command -v pipx --version 2> /dev/null)
POETRY := $(shell command -v poetry 2> /dev/null)
OTTERDOG_SCRIPT := $(realpath ./otterdog.sh)
OTTERDOG_LINK := ~/.local/bin/otterdog
VERSION := $(shell poetry version -s)
HOST_HW_PLATFORM := $(shell uname -m)

all: help

init:  ## Initialize the development environment
ifndef PIPX
	$(error "Please install pipx first, e.g. using 'apt install pipx' or 'brew install pipx")
endif

ifndef POETRY
	pipx install "poetry>=2.0.1"
endif

	poetry config virtualenvs.in-project true
	poetry dynamic-versioning show || poetry sync --only-root
	poetry sync
	poetry run python -m playwright install firefox

	test -f $(OTTERDOG_LINK) || ln -s $(OTTERDOG_SCRIPT) $(OTTERDOG_LINK)

test:  ## Run tests
	poetry run pytest

clean:  ## Clean the development environment
	rm -rf .venv
	rm -rf dist
	rm -rf .pytest_cache
	git clean -X -d -f

build-image:  ## Build container image
	docker build -f docker/Dockerfile --build-arg version=$(VERSION) -t ghcr.io/eclipse-csi/otterdog:1.0.1 .

init-minikube:
	@if ! minikube status >/dev/null 2>&1; then \
		echo "Starting minikube..."; \
		minikube start --driver=docker; \
		echo "Enabling required addons..."; \
		minikube addons enable ingress; \
		minikube addons enable ingress-dns; \
		sleep 3; \
	else \
		echo "Minikube is already running."; \
		if [ "$$(minikube addons list -o json | jq .ingress.Status)" != "\"enabled\"" ]; then \
			echo "Enabling ingress addon..."; \
			minikube addons enable ingress; \
			sleep 3; \
		fi; \
		if [ "$$(minikube addons list -o json | jq '."ingress-dns".Status')" != "\"enabled\"" ]; then \
			echo "Enabling ingress-dns addon..."; \
			minikube addons enable ingress-dns; \
			sleep 3; \
		fi; \
	fi

dev-webapp:  ## Run full stack development (includes webapp)
	$(MAKE) init-minikube
	eval $$(minikube -p minikube docker-env)
	@if [ "$(HOST_HW_PLATFORM)" = "arm64" ]; then \
		skaffold dev --filename=dev/skaffold.yaml --profile dev-arm64; \
	else \
		skaffold dev --filename=dev/skaffold.yaml --profile dev; \
	fi

dev-webapp-tunnel:  ## Run full stack development (includes webapp)
	$(MAKE) init-minikube
	eval $$(minikube -p minikube docker-env)
	@if [ "$(HOST_HW_PLATFORM)" = "arm64" ]; then \
		skaffold dev --filename=dev/skaffold.yaml --profile dev-tunnel-arm64; \
	else \
		skaffold dev --filename=dev/skaffold.yaml --profile dev-tunnel; \
	fi

clean-webapp:  ## Clean Web App the development environment
	@minikube delete

help:  ## Show this help
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
