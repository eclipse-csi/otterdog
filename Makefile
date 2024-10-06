.PHONY: init test clean

POETRY := $(shell command -v poetry 2> /dev/null)
OTTERDOG_SCRIPT := $(realpath ./otterdog.sh)
OTTERDOG_LINK := ~/.local/bin/otterdog

init:
ifndef POETRY
	pip3 install "poetry==1.8.3"
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
