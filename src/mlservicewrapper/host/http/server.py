import asyncio
import threading

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

import logging


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

class _ApiInstance:
    def __init__(self):
        self._load_error = False
        self._is_ready = False
        self._status_message = "Loading..."
        self._service: mlservicewrapper.core.services.Service = None

    def on_stopping(self):
        if not self._is_ready and hasattr(self._service, 'dispose'):
            self._service.dispose()
        
    async def _do_load_async(self):
        try:
            print("load")
            service, config_parameters = mlservicewrapper.core.server.get_service_instance()

            if hasattr(service, 'load'):
                context = mlservicewrapper.core.contexts.EnvironmentVariableServiceContext("SERVICE_", config_parameters)

                print("service.load")
                await service.load(context)

            self._service = service
            self._is_ready = True
            self._status_message = "Ready!"
        except:
            self._load_error = True
            self._status_message = "Error during load!"
            raise
        finally:
            print("done load")
        
    def begin_loading(self):
        def run():
            loop = asyncio.new_event_loop()
            c = self._do_load_async()
            loop.run_until_complete(c)

        thr = threading.Thread(target=run)
        thr.daemon = True
        thr.start()

        print("Done begin_loading")

    async def process_batch(self, request: Request) -> Response:
        content_type = "application/json"
        # request.headers.get("Content-Type", "application/json")

        if content_type.lower() == "application/json":
            req_dict = await request.json()

            req_ctx = _HttpJsonProcessContext(req_dict.get("parameters", dict()), req_dict.get("inputs", dict()))

            logging.debug("parsed request body...")
        else:
            return _error_response(405, "This endpoint does not accept {}!".format(content_type))

        if not self._is_ready:
            return _error_response(503, "The model is still loading!")

        try:
            await self._service.process(req_ctx)
        except mlservicewrapper.core.errors.BadParameterError as err:
            return _bad_request_response(err.message, "parameter", err.name)
        except mlservicewrapper.core.errors.DatasetFieldError as err:
            return _bad_request_response(err.message, "dataset", err.name, { "field": err.field_name })
        except mlservicewrapper.core.errors.BadDatasetError as err:
            return _bad_request_response(err.message, "dataset", err.name)
        except mlservicewrapper.core.errors.BadRequestError as err:
            return _bad_request_response(err.message)

        outputs_dict = dict(((k, v.to_dict("records")) for k, v in req_ctx.output_dataframes()))

        logging.debug("returning response...")

        return JSONResponse({
            "outputs": outputs_dict
        })

    def get_status(self, request: Request):
        
        return JSONResponse({"status": self._status_message, "ready": self._is_ready}, 200)


    def decorate_app(self, starlette_app: Starlette, route_prefix: str):
        starlette_app.add_route(route_prefix + "status", self.get_status, methods=["GET"])
        starlette_app.add_route(route_prefix + "process/batch", self.process_batch, methods=["POST"])


_api = _ApiInstance()

app = Starlette(debug=True, on_startup=[_api.begin_loading], on_shutdown=[_api.on_stopping])

_api.decorate_app(app, "/api/")
