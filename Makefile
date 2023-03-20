.PHONY: init test clean

bw_version = "bw-linux-2023.2.0.zip"
bw_release = "cli-v2023.2.0"
dockerfile = "Dockerfile"
image_base = "ubuntu"
image_version = "dev"
container_name = "otterdog"

POETRY := $(shell command -v dot 2> /dev/null)

init:
ifndef POETRY
	pip3 install "poetry==1.4.0"
endif
	poetry config virtualenvs.in-project true
	poetry install --only=main --no-root
	poetry run playwright install firefox

test:
	poetry run py.test

clean:
	rm -rf .venv
	rm -rf dist
	rm -rf .pytest_cache
	find -iname "*.pyc" -delete


docker_build:
	docker build  --no-cache --build-arg BW_VERSION=$(bw_version) --build-arg BW_RELEASE=$(bw_release) -t eclipse/otterdog:latest-$(image_base) -f $(dockerfile) .

docker_clean:
	docker rm -f $(container_name)-$(image_base)
	docker rmi -f eclipse/$(container_name):latest-$(image_base)
