HOW TO: DOCKER CONTAINER
-----------------------

INTRODUCTION
============
Please find below list of HOW-TOs about otterdog docker container

HOW TO: RUNNING OTTERDOG CONTAINER AS SERVICE USING BW (MacOS/Linux)
======================================================
* Firstly, please comment entroy point line from [Dockerfile](../../Dockerfile) without tracking in git by using the snippet below
```console
git update-index --assume-unchanged $(dockerfile)
sed -i '/^ENTRYPOINT/ s/./#&/' Dockerfile
```
* Then, please build a new docker image
* After that, please unlock bw by executing ```bw unlock``` and follow the instractions about BW_SESSION variable, you may find out a line similar to this one below ```export BW_SESSION="lorepipsum!!2@@@3··4fdsatree"```
* Then, please revert changes done in [Dockerfile](../../Dockerfile) by using snippet below
```console
sed -i '/^#ENTRYPOINT/ s/#//' Dockerfile
git update-index --no-assume-unchanged Dockerfile
```
* Last but not least, run a new docker image as service based on bash snippet below and check out that you have a container called
```console
docker run --rm -idt --name $container_name-ubuntu --hostname $container_name-ubuntu -e BW_SESSION="${BW_SESSION}" -v $HOME/.config/Bitwarden\ CLI/data.json:/root/.config/Bitwarden\ CLI/data.json -v $PWD/otterdog.json:/app/otterdog.json -v $PWD/orgs:/app/orgs eclipse/otterdog:latest-ubuntu /bin/bash
```
* Finally, access into docker container using a bash snippet below
```console
docker exec -it otterdog-ubuntu /bin/bash
```
**PS:** Please bear in mind to remove an otterdog container after using by executing ```docker rm -f otterdog-ubuntu```