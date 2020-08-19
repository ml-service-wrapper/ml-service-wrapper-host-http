FROM tiangolo/uvicorn-gunicorn-starlette:python3.8 as base

# FROM tiangolo/uvicorn-gunicorn-machine-learning:python3.7 as base
#RUN pip install starlette

COPY ./src/core /lib/mlservicewrapper/core

RUN pip install /lib/mlservicewrapper/core

FROM base as final

ENV SERVICE_CONFIG_PATH=/app/service/config.json

COPY ./src/http_api /app/

COPY ./sample/1_simple /app/service

