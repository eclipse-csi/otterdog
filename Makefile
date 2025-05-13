.PHONY: init test clean

PIPX := $(shell command -v pipx --version 2> /dev/null)
POETRY := $(shell command -v poetry 2> /dev/null)
OTTERDOG_SCRIPT := $(realpath ./otterdog.sh)
OTTERDOG_LINK := ~/.local/bin/otterdog


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

help:  ## Show this help
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
