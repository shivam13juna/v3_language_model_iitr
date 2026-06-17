
**Build images**

* `docker build -t oct8 .`
* `docker build -t oct9 .`
* `docker build -t oct8_v2 .`

**Auth & inspection**

* `docker login`
* `docker image ls`
* `docker image ls | head`  *(list images, then trim output)*
* `docker container ls`     *(show running containers)*

**Run containers (mapping host → container port)**

* `docker run -p 8000:8000 oct8`            *(host 8000 → container 8000)*
* `docker run -p 9000:8000 oct8`            *(host 9000 → container 8000)*
* `docker run -d -p 9000:8000 oct8`         *(detached)*
* `docker run -it -p 9000:8000 oct8 bash`   *(interactive shell in the container)*

**Tag & push to Docker Hub**

* `docker tag oct8_v2:latest shivam13juna/docker_oct8:latest`
* `docker push shivam13juna/docker_oct8:latest`

---


#export PATH="/Users/shivam13juna/Library/Python/3.9/bin:$PATH"

export VIRTUALENVWRAPPER_PYTHON=/opt/homebrew/bin/python3
export WORKON_HOME=~/Documents/virtual_envs
export VIRTUALENVWRAPPER_VIRTUALENV=/opt/homebrew/bin/virtualenv
source /opt/homebrew/bin/virtualenvwrapper.sh