from .server import app
import gunicorn.app.base

class _StandaloneApplication(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

        self.cfg.set('worker_class', 'uvicorn.workers.UvicornWorker')
        

    def load(self):
        return self.application

def run_with_gunicorn(host: str, port: int, workers: int = 2):
    options = {
        'bind': '%s:%s' % (host, port),
        'workers': workers
    }

    _StandaloneApplication(app, options).run()

