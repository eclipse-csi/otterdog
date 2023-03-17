bw_version = "bw-linux-2023.2.0.zip"
bw_release = "cli-v2023.2.0"
dockerfile = "Dockerfile"
image_base = "ubuntu"
image_version = "dev"
container_name = "otterdog"

init:
	test -d venv || python3 -m venv venv
	( \
		. venv/bin/activate; \
		pip3 install -r requirements.txt; \
		playwright install chromium \
	)

test:
	( \
		. venv/bin/activate; \
		pytest tests \
	)

clean:
	rm -rf venv
	find -iname "*.pyc" -delete

.PHONY: init test clean

docker_build:
	docker build  --no-cache --build-arg BW_VERSION=$(bw_version) --build-arg BW_RELEASE=$(bw_release) -t eclipse/otterdog:latest-$(image_base) -f $(dockerfile) .

docker_clean:
	docker rm -f $(container_name)-$(image_base)
	docker rmi -f eclipse/$(container_name):latest-$(image_base)

docker_test_container:
	echo "Please unlock BW"
	`bw unlock | grep -o 'export.*$$'`
	echo "Freezing $(dockerfile) and commenting ENTRYPOINT line"
	git update-index --assume-unchanged $(dockerfile)
	sed -i '/^ENTRYPOINT/ s/./#&/' Dockerfile
	docker build  --no-cache --build-arg BW_VERSION=$(bw_version) --build-arg BW_RELEASE=$(bw_release) -t eclipse/otterdog:latest-$(image_base) -f $(dockerfile) .
	echo "Unfreezing $(dockerfile) and commenting ENTRYPOINT line"
	sed -i '/^#ENTRYPOINT/ s/#//' Dockerfile
	git update-index --no-assume-unchanged Dockerfile
	docker run --rm -idt --name $(container_name)-$(image_base) --hostname $(container_name)-$(image_base) -e BW_SESSION="${BW_SESSION}" -v $$HOME/.config/Bitwarden\ CLI/data.json:/root/.config/Bitwarden\ CLI/data.json -v $$PWD/otterdog.json:/app/otterdog.json -v $$PWD/orgs:/app/orgs eclipse/otterdog:latest-$(image_base) /bin/bash
	docker exec -it otterdog-ubuntu /bin/bash