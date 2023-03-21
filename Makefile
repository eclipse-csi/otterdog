.PHONY: init test clean container_build container_clean

bw_version = "bw-linux-2023.2.0.zip"
bw_release = "cli-v2023.2.0"
dockerfile = "Dockerfile"
image_version = "latest"
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


container_build:
	$(call CONTAINER_BUILDER,$(image_version))

container_build_dev:
	echo "Freezing $(dockerfile) and commenting ENTRYPOINT line"
	git update-index --assume-unchanged $(dockerfile)
	sed -i '/^ENTRYPOINT/ s/./#&/' Dockerfile
	$(call CONTAINER_BUILDER,"dev")
	echo "Unfreezing $(dockerfile) and commenting ENTRYPOINT line"
	sed -i '/^#ENTRYPOINT/ s/#//' Dockerfile
	git update-index --no-assume-unchanged Dockerfile


container_clean:
	$(call CONTAINER_CLEANER,$(image_version))

container_clean_dev: 
	$(call CONTAINER_CLEANER,"dev")

define CONTAINER_BUILDER
	docker build  --no-cache --build-arg BW_VERSION=$(bw_version) --build-arg BW_RELEASE=$(bw_release) -t eclipse/otterdog:$(1) -f $(dockerfile) .
endef

define CONTAINER_CLEANER
	docker rm -f $(container_name)
	docker rmi -f eclipse/$(container_name):$(1)
endef
