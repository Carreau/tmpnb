## tmpnb

[![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/jupyter/tmpnb?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Launches "temporary" IPython notebook servers.

#### :warning: Hardware assumptions :warning:

* Reasonably fast IOPS (SSDs, PCIe cards)
* Enough CPUs and memory for all the users (`mem_limit`*`pool_size` < Available RAM)

#### Quick start

Get Docker, then:

```
docker pull jupyter/demo
export TOKEN=$( head -c 30 /dev/urandom | xxd -p )
docker run --net=host -d -e CONFIGPROXY_AUTH_TOKEN=$TOKEN jupyter/configurable-http-proxy --default-target http://127.0.0.1:9999
docker run --net=host -d -e CONFIGPROXY_AUTH_TOKEN=$TOKEN -v /var/run/docker.sock:/docker.sock jupyter/tmpnb
```

BAM! Visit your host on port 8000 and you have a working tmpnb setup.

#### Advanced configuration

If you need to set the `docker-version` or other options, they can be passed to `jupyter/tmpnb` directly:

```
docker run --net=host -d -e CONFIGPROXY_AUTH_TOKEN=$TOKEN -v /var/run/docker.sock:/docker.sock jupyter/tmpnb python orchestrate.py --cull-timeout=60 --docker-version="1.13"
```

#### Installation

If doing direct installation, you'll need to install it within `/srv/tmpnb` on Ubuntu 14.04.

```
mkdir -p /srv/
cd /srv/
git clone https://github.com/jupyter/tmpnb.git
cd tmpnb
script/bootstrap
```

The running user needs permission on the Docker socket.

#### Development

```
git clone https://github.com/jupyter/tmpnb.git
cd tmpnb

# If modifying the Docker image in any way
docker build -t jupyter/demo images/demo

pip install -r requirements.txt
npm install jupyter/configurable-http-proxy

# Kick off the proxy and run the server.
# Runs on all interfaces on port 8000 by default.
script/dev
```
