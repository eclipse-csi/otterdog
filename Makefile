.PHONY: init test check clean build-image init-minikube check-kube-context dev-webapp dev-webapp-ts dev-webapp-tunnel dev-webapp-tunnel-local dev-webapp-ngrok dev-webapp-ngrok-local clean-ingress-finalizers clean-tailscale-proxies clean-webapp docs docs-serve docs-serve-dev docs-serve-tunnel docs-serve-ngrok playground-examples help

PIPX := $(shell command -v pipx --version 2> /dev/null)
POETRY := $(shell command -v poetry 2> /dev/null)
OTTERDOG_SCRIPT := $(realpath ./otterdog.sh)
OTTERDOG_TS_CLEAN_SCRIPT := $(realpath ./dev/scripts/remove-ts-machines.sh)
OTTERDOG_LINK := ~/.local/bin/otterdog
VERSION := $(shell poetry version -s)
# url of the webapp started with `make dev-webapp`, reachable after `kubectl port-forward -n otterdog deploy/otterdog 5000:5000`
OTTERDOG_DEV_URL ?= http://localhost:5000
# address of the documentation served with `make docs-serve*`, the Playground of the webapp started with
# `make dev-webapp*` links its examples to it
DOCS_DEV_ADDR ?= 127.0.0.1:8000
DOCS_DEV_URL ?= http://$(DOCS_DEV_ADDR)/
# kubectl context of the minikube cluster, the only context the development targets may deploy to
MINIKUBE_CONTEXT := minikube

all: help

init:  ## Initialize the development environment
ifndef POETRY
	ifndef PIPX
		$(error Poetry not found, and pipx is also not installed. \
\
To install Poetry, you can either: \
\
1. Install pipx first: \
   - On Debian/Ubuntu: apt install pipx \
   - On macOS: brew install pipx \
   Then run 'make init' again, which will use pipx to install Poetry. \
\
2. Install Poetry directly: \
   curl -sSL https://install.python-poetry.org | python3 -)
	endif

	pipx install "poetry>=2.0.1"
endif

	poetry config virtualenvs.in-project true
	poetry dynamic-versioning show || poetry sync --only-root
	poetry sync
	poetry run python -m playwright install firefox

	@[ "$$(readlink -f $(OTTERDOG_LINK) 2>/dev/null)" = "$(OTTERDOG_SCRIPT)" ] \
		|| { ln -sf $(OTTERDOG_SCRIPT) $(OTTERDOG_LINK); echo "Updated symlink: $(OTTERDOG_LINK) -> $(OTTERDOG_SCRIPT)"; }

test:  ## Run tests with coverage
	poetry run pytest -rs tests --cov=otterdog --cov-report=term --cov-report=html

clean:  ## Clean the development environment
	rm -rf .venv
	rm -rf dist
	rm -rf .pytest_cache
	git clean -X -d -f

build-image:  ## Build container image
	docker build -f docker/Dockerfile --build-arg version=$(VERSION) -t ghcr.io/eclipse-csi/otterdog:$(VERSION) .

init-minikube:
	helm repo update || true
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
	@$(MAKE) --no-print-directory check-kube-context

check-kube-context:  ## Fail if the current kubectl context is not the one of minikube
	@current="$$(kubectl config current-context 2>/dev/null)"; \
	if [ "$$current" != "$(MINIKUBE_CONTEXT)" ]; then \
		echo "Error: the current kubectl context is '$${current:-<none>}' instead of '$(MINIKUBE_CONTEXT)'."; \
		echo "The development targets deploy to the current context, switch to minikube first:"; \
		echo "  kubectl config use-context $(MINIKUBE_CONTEXT)"; \
		exit 1; \
	fi

dev-webapp: init-minikube clean-ingress-finalizers ## Run full stack development (includes webapp)
	eval $$(minikube -p minikube docker-env)
	DOCS_DEV_URL="$(DOCS_DEV_URL)" skaffold dev --filename=dev/skaffold.yaml --profile dev --cleanup=false

clean-ingress-finalizers: check-kube-context  ## Remove finalizers from stuck ingress objects and wait for namespace deletion
	@if kubectl get namespace otterdog -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Terminating; then \
	  echo "Namespace otterdog stuck in Terminating, cleaning up..."; \
	  kubectl get ingress -n otterdog -o name 2>/dev/null | \
	    xargs --no-run-if-empty -I{} kubectl patch {} -n otterdog \
	    -p '{"metadata":{"finalizers":[]}}' --type=merge 2>/dev/null || true; \
	  kubectl wait --for=delete namespace/otterdog --timeout=30s 2>/dev/null || true; \
	fi

clean-tailscale-proxies: check-kube-context  ## Delete stale tailscale proxy StatefulSets
	@kubectl delete statefulsets -n tailscale --all --ignore-not-found 2>/dev/null || true

dev-webapp-tunnel: init-minikube clean-ingress-finalizers clean-tailscale-proxies  ## Run full stack development (includes webapp)
	eval $$(minikube -p minikube docker-env)
	DOCS_DEV_URL="$(DOCS_DEV_URL)" skaffold dev --filename=dev/skaffold.yaml --profile dev-tunnel --cleanup=false

dev-webapp-tunnel-local: init-minikube clean-ingress-finalizers clean-tailscale-proxies  ## Run full stack development (includes webapp)
	eval $$(minikube -p minikube docker-env)
	DOCS_DEV_URL="$(DOCS_DEV_URL)" skaffold dev --filename=dev/skaffold.yaml --profile dev-tunnel-local --cleanup=false

dev-webapp-ngrok: init-minikube clean-ingress-finalizers  ## Run full stack development (includes webapp), exposed via ngrok
	eval $$(minikube -p minikube docker-env)
	DOCS_DEV_URL="$(DOCS_DEV_URL)" skaffold dev --filename=dev/skaffold.yaml --profile dev-ngrok --cleanup=true

dev-webapp-ngrok-local: init-minikube clean-ingress-finalizers  ## Run full stack development (includes webapp), exposed via ngrok, using local Helm chart checkout
	eval $$(minikube -p minikube docker-env)
	DOCS_DEV_URL="$(DOCS_DEV_URL)" skaffold dev --filename=dev/skaffold.yaml --profile dev-ngrok-local --cleanup=false

check:  ## Run all pre-commit checks
	poetry run prek -a

clean-webapp:  ## Clean Web App the development environment
	@minikube delete
	bash $(OTTERDOG_TS_CLEAN_SCRIPT)

docs:  ## Generate documentation
	poetry run mkdocs build

docs-serve:  ## Serve the documentation, Playground links target $OTTERDOG_URL (default: https://otterdog.eclipse.org)
	poetry run mkdocs serve --livereload --dev-addr "$(DOCS_DEV_ADDR)"

docs-serve-dev:  ## Serve the documentation, Playground links target the webapp of `make dev-webapp` ($OTTERDOG_DEV_URL)
	OTTERDOG_URL="$(OTTERDOG_DEV_URL)" poetry run mkdocs serve --livereload --dev-addr "$(DOCS_DEV_ADDR)"

docs-serve-tunnel:  ## Serve the documentation, Playground links target the webapp of `make dev-webapp-tunnel*` (tailscale)
	@if [ -z "$$TS_DNS" ]; then echo 'Error: TS_DNS is not set'; exit 1; fi
	OTTERDOG_URL="https://otterdog.$$TS_DNS" poetry run mkdocs serve --livereload --dev-addr "$(DOCS_DEV_ADDR)"

docs-serve-ngrok:  ## Serve the documentation, Playground links target the webapp of `make dev-webapp-ngrok*`
	@if [ -z "$$NGROK_DOMAIN" ]; then echo 'Error: NGROK_DOMAIN is not set'; exit 1; fi
	OTTERDOG_URL="https://$$NGROK_DOMAIN" poetry run mkdocs serve --livereload --dev-addr "$(DOCS_DEV_ADDR)"

playground-examples:  ## Update the examples listed by the Playground from the configuration guides
	poetry run python docs/hooks/playground.py

help:  ## Show this help
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
