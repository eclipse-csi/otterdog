.PHONY: init test clean

PIPX := $(shell command -v pipx --version 2> /dev/null)
POETRY := $(shell command -v poetry 2> /dev/null)
OTTERDOG_SCRIPT := $(realpath ./otterdog.sh)
OTTERDOG_LINK := ~/.local/bin/otterdog

init:
ifndef PIPX
	$(error "Please install pipx first, e.g. using 'apt install pipx'")
endif

ifndef POETRY
	pipx install "poetry==1.8.5"
	pipx inject poetry "poetry-dynamic-versioning[plugin]"
endif

	poetry config virtualenvs.in-project true
	poetry install --only=main
	poetry run playwright install firefox

	test -f $(OTTERDOG_LINK) || ln -s $(OTTERDOG_SCRIPT) $(OTTERDOG_LINK)

test:
	poetry run py.test

clean:
	rm -rf .venv
	rm -rf dist
	rm -rf .pytest_cache
	find -iname "*.pyc" -delete
