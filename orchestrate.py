#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os
import uuid

from concurrent.futures import ThreadPoolExecutor

import tornado
import tornado.options
from tornado.log import app_log
from tornado.web import RequestHandler

from tornado import gen, web
from tornado import ioloop

import dockworker
import spawnpool


class LoadingHandler(RequestHandler):
    def get(self, path=None):
        self.render("loading.html", path=path)


class SpawnHandler(RequestHandler):

    @gen.coroutine
    def get(self, path=None):
        '''Spawns a brand new server'''

        try:
            if path is None:
                # No path. Assign a prelaunched container from the pool and redirect to it.
                # Append self.redirect_uri to the redirect target.
                container_path = self.pool.acquire().path
                app_log.info("Allocated [%s] from the pool.", container_path)

                url = "/{}/{}".format(container_path, self.redirect_uri)
            else:
                path_parts = path.lstrip('/').split('/', 1)
                container_path = path_parts[0]

                # Scrap a container from the pool and replace it with an ad-hoc replacement.
                # This takes longer, but is necessary to support ad-hoc containers
                yield self.pool.adhoc(container_path)

                app_log.info("Allocated ad-hoc container at [%s].", container_path)
                url = path

            app_log.debug("Redirecting [%s] -> [%s].", self.request.path, url)
            self.redirect(url, permanent=False)
        except spawnpool.EmptyPoolError:
            app_log.warning("The container pool is empty!")
            self.render("full.html", cull_period=self.cull_period)

    @property
    def pool(self):
        return self.settings['pool']

    @property
    def cull_period(self):
        return self.settings['cull_period']

    @property
    def redirect_uri(self):
        return self.settings['redirect_uri']

def main():
    tornado.options.define('cull_period', default=600,
        help="Interval (s) for culling idle containers."
    )
    tornado.options.define('cull_timeout', default=3600,
        help="Timeout (s) for culling idle containers."
    )
    tornado.options.define('container_ip', default='127.0.0.1',
        help="IP address for containers to bind to"
    )
    tornado.options.define('container_port', default='8888',
        help="Port for containers to bind to"
    )
    tornado.options.define('ipython_executable', default='ipython3',
        help="IPython Notebook startup (e.g. ipython, ipython2, ipython3)"
    )
    tornado.options.define('port', default=9999,
        help="port for the main server to listen on"
    )
    tornado.options.define('max_dock_workers', default=24,
        help="Maximum number of docker workers"
    )
    tornado.options.define('mem_limit', default="512m",
        help="Limit on Memory, per container"
    )
    tornado.options.define('cpu_shares', default=None,
        help="Limit CPU shares, per container"
    )
    tornado.options.define('image', default="jupyter/demo",
        help="Docker container to spawn for new users. Must be on the system already"
    )
    tornado.options.define('docker_version', default="1.13",
        help="Version of the Docker API to use"
    )
    tornado.options.define('redirect_uri', default="/tree",
        help="URI to redirect users to upon initial notebook launch"
    )
    tornado.options.define('pool_size', default=128,
        help="Capacity for containers on this system. Will be prelaunched at startup."
    )

    tornado.options.parse_command_line()
    opts = tornado.options.options

    handlers = [
        (r"/", LoadingHandler),
        (r"/spawn/?(/user-\w+(?:/.*)?)?", SpawnHandler),
        (r"/(user-\w+)(?:/.*)?", LoadingHandler),
    ]

    proxy_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
    proxy_endpoint = os.environ.get('CONFIGPROXY_ENDPOINT', "http://127.0.0.1:8001")
    docker_host = os.environ.get('DOCKER_HOST', 'unix://var/run/docker.sock')

    max_age = datetime.timedelta(seconds=opts.cull_timeout)

    container_config = dockworker.ContainerConfig(
        image=opts.image,
        ipython_executable=opts.ipython_executable,
        mem_limit=opts.mem_limit,
        cpu_shares=opts.cpu_shares,
        container_ip=opts.container_ip,
        container_port=opts.container_port
    )

    spawner = dockworker.DockerSpawner(docker_host,
                                       version=opts.docker_version,
                                       timeout=20,
                                       max_workers=opts.max_dock_workers)

    pool = spawnpool.SpawnPool(proxy_endpoint=proxy_endpoint,
                               proxy_token=proxy_token,
                               spawner=spawner,
                               container_config=container_config,
                               capacity=opts.pool_size,
                               max_age=max_age)

    ioloop = tornado.ioloop.IOLoop().instance()

    settings = dict(
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        cookie_secret=uuid.uuid4(),
        xsrf_cookies=True,
        debug=True,
        cull_period=opts.cull_period,
        spawner=spawner,
        pool=pool,
        autoescape=None,
        proxy_token=proxy_token,
        template_path=os.path.join(os.path.dirname(__file__), 'templates'),
        proxy_endpoint=proxy_endpoint,
        redirect_uri=opts.redirect_uri.lstrip('/'),
    )

    # Synchronously cull any existing, inactive containers, and pre-launch a set number of
    # containers, ready to serve.
    ioloop.run_sync(pool.heartbeat)

    # Periodically execute a heartbeat function to cull used containers and regenerated failed
    # ones, self-healing the cluster.
    cull_ms = opts.cull_period * 1e3
    app_log.info("Culling containers unused for %i seconds every %i seconds.",
                 opts.cull_timeout,
                 opts.cull_period)
    culler = tornado.ioloop.PeriodicCallback(pool.heartbeat, cull_ms)
    culler.start()

    app_log.info("Listening on {}".format(opts.port))
    application = tornado.web.Application(handlers, **settings)
    application.listen(opts.port)
    ioloop.start()

if __name__ == "__main__":
    main()
