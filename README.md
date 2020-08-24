
[![Release](https://github.com/ml-service-wrapper/ml-service-wrapper-host-http/workflows/Create%20Release/badge.svg)](https://github.com/ml-service-wrapper/ml-service-wrapper-host-http/releases/latest)
[![PyPI Latest Release](https://img.shields.io/pypi/v/mlservicewrapper-host-http.svg)](https://pypi.org/project/mlservicewrapper-host-http/)

Host an [`mlservicewrapper.core.services.Service`](https://github.com/ml-service-wrapper/ml-service-wrapper-core) as an HTTP API.

# Command Line Arguments

| Parameter | Required? | Description | Format |
| --------------- | --------------- | --------------- | --------------- |
| --config | **Yes** | Path to service configuration file. | `--config <path>` |
| --host | No | The hostname to bind to. Defaults to 127.0.0.1. | `--host <host name>` |
| --port | No | The post to bind to. Defaults to 5000. | `--post <port number>` |
| --workers | No | The number of workers to deploy when using gunicorn. Defaults to 2. | `--workers <count>` |
| --prod | No | A flag to indicate if running as production. Enabling this flag switches to use gunicorn (instead of the default uvicorn), meaning it's a more reliable and performant option. | `--prod` |
