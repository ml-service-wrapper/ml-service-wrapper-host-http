FROM tiangolo/uvicorn-gunicorn-starlette:python3.8 as base

# FROM tiangolo/uvicorn-gunicorn-machine-learning:python3.7 as base
#RUN pip install starlette

RUN pip install mlservicewrapper-host-http

ENV SERVICE_CONFIG_PATH=/app/service/config.json

COPY ./sample/1_simple /app/service

