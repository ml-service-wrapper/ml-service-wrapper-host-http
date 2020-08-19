import asyncio
import concurrent
import concurrent.futures
import importlib
import json
import os
# from multiprocessing import Manager, Value
import threading
import time

import mlservicewrapper
import mlservicewrapper.core
import mlservicewrapper.core.contexts
import mlservicewrapper.core.errors
import mlservicewrapper.core.server
import mlservicewrapper.core.services
import pandas as pd
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


def _error_response(status_code: int, message: str):
    return JSONResponse({"error": message}, status_code)

def _bad_request_response(message: str, input_type: str = None, name: str = None, additional_details: dict = None):
    return JSONResponse({
        "error": "An invalid value was provided to {}.".format(name),
        "inputType": input_type,
        "name": name,
        "details": message,
        "additionalInformation": additional_details
    }, 400)

class _HttpJsonProcessContext(mlservicewrapper.core.contexts.CollectingProcessContext):
    def __init__(self, parameters: dict, inputs: dict):
        super().__init__()
        self.__parameters = parameters or dict()
        self.__inputs = inputs or dict()

    def get_parameter_value(self, name: str, required: bool = True, default: str = None) -> str:
        mlservicewrapper.core.contexts.NameValidator.raise_if_invalid(name)

        if name in self.__parameters:
            return self.__parameters[name]

        if required and default is None:
            raise mlservicewrapper.core.errors.MissingParameterError(name)

        return default
    

    async def get_input_dataframe(self, name: str, required: bool = True):
        if name in self.__inputs:
            return pd.DataFrame.from_records(self.__inputs[name])

        if required:
            raise mlservicewrapper.core.errors.MissingDatasetError(name)

        return None

_load_error = False
_is_ready = False
_status_message = "Loading..."
_service: mlservicewrapper.core.services.Service = None

async def _process_batch(request: Request) -> Response:
    content_type = "application/json"
    # request.headers.get("Content-Type", "application/json")

    if content_type.lower() == "application/json":
        req_dict = await request.json()

        req_ctx = _HttpJsonProcessContext(req_dict.get("parameters", dict()), req_dict.get("inputs", dict()))
    else:
        return _error_response(405, "This endpoint does not accept {}!".format(content_type))

    if not _is_ready:
        return _error_response(503, "The model is still loading!")

    try:
        await _service.process(req_ctx)
    except mlservicewrapper.core.errors.BadParameterError as err:
        return _bad_request_response(err.message, "parameter", err.name)
    except mlservicewrapper.core.errors.DatasetFieldError as err:
        return _bad_request_response(err.message, "dataset", err.name, { "field": err.field_name })
    except mlservicewrapper.core.errors.BadDatasetError as err:
        return _bad_request_response(err.message, "dataset", err.name)
    except mlservicewrapper.core.errors.BadRequestError as err:
        return _bad_request_response(err.message)

    outputs_dict = dict(((k, v.to_dict("records")) for k, v in req_ctx.output_dataframes()))
    
    return JSONResponse({
        "outputs": outputs_dict
    })

def _get_status(request: Request):
    
    return JSONResponse({"status": _status_message, "ready": _is_ready}, 200)

def _on_stopping():
    if not _is_ready and hasattr(_service, 'dispose'):
        _service.dispose()
    
async def _do_load_async():
    global _service
    global _status_message
    global _is_ready
    global _load_error

    try:
        print("load")
        service, config_parameters = mlservicewrapper.core.server.get_service_instance()

        if hasattr(service, 'load'):
            context = mlservicewrapper.core.contexts.EnvironmentVariableServiceContext("SERVICE_", config_parameters)

            print("service.load")
            await service.load(context)

        _service = service
        _is_ready = True
        _status_message = "Ready!"
    except:
        _load_error = True
        _status_message = "Error during load!"
        raise
    finally:
        print("done load")
    
def _begin_loading():
    
    def run():
        global _loading_future

        loop = asyncio.new_event_loop()
        _loading_future = _do_load_async()
        loop.run_until_complete(_loading_future)

    thr = threading.Thread(target=run)
    thr.daemon = True
    thr.start()

    print("Done begin_loading")

_routes = [
    Route("/api/process/batch", endpoint=_process_batch, methods=["POST"]),
    Route("/api/status", endpoint=_get_status, methods=["GET"])
]

app = Starlette(debug=True, routes=_routes, on_startup=[_begin_loading], on_shutdown=[_on_stopping])

# print("begin_loading")
# api.begin_loading()

# print("done begin_loading!")

# time.sleep(60)

# print("done sleep")
