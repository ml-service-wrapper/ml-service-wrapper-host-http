
[![Release](https://github.com/ml-service-wrapper/ml-service-wrapper-host-http/workflows/Create%20Release/badge.svg)](https://github.com/ml-service-wrapper/ml-service-wrapper-host-http/releases/latest)
[![PyPI Latest Release](https://img.shields.io/pypi/v/mlservicewrapper-host-http.svg)](https://pypi.org/project/mlservicewrapper-host-http/)

Host an [`mlservicewrapper.core.services.Service`](https://github.com/ml-service-wrapper/ml-service-wrapper-core) as an HTTP API.

# Testing locally

Using the development server is sufficient for testing, but should not be used in production.

## Command Line Arguments

| Parameter | Required? | Description | Format |
| --------------- | --------------- | --------------- | --------------- |
| --config | **Yes** | Path to service configuration file. | `--config <path>` |
| --host | No | Host to bind to. Defaults to 127.0.0.1. | `--host <host name>` |
| --port | No | Port to bind to. Defaults to 5000. | `--host <host name>` |


# Deployment

Use [gunicorn](https://docs.gunicorn.org/en/stable/deploy.html) to run in production:

```bash
export SERVICE_CONFIG_PATH=/path/to/config.json
gunicorn -w 4 -k uvicorn.workers.UvicornWorker mlservicewrapper.host.http
```
