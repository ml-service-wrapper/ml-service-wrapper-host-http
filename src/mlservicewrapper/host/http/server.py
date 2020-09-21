import asyncio
import threading
import typing

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

class _ObjectSchema:
    def __init__(self):
        self.__properties = dict()
        self.__required = []

    def add_property(self, name: str, schema: dict, required: bool):
        self.__properties[name] = schema

        if required:
            self.__required.append(name)

    def has_required_properties(self):
        return len(self.__required) > 0

    def has_properties(self):
        return len(self.__properties) > 0

    def to_dict(self) -> dict:
        schema = {
            "type": "object",
            "properties": self.__properties
        }

        if self.has_required_properties():
            schema["required"] = self.__required
        
        return schema

class _SwaggerBuilder:
    def _append_datasets(self, to_schema: _ObjectSchema, direction: str, field: str, specs: typing.Dict[str, dict]):
        
        datasets_schema = _ObjectSchema()

        for name, spec in specs.items():
            item_schema = spec.get("itemSchema")

            if item_schema is None:
                continue

            datasets_schema.add_property(name, {
                "type": "array",
                "title": f"{name} {direction} dataset",
                "items": item_schema
            }, spec.get("required", True))

        if not datasets_schema.has_properties():
            return False

        to_schema.add_property(field, datasets_schema.to_dict(), datasets_schema.has_required_properties())

        return True

    def _append_process_parameters_schema(self, to_schema: _ObjectSchema, service: mlservicewrapper.core.server.ServerInstance):

        process_parameters_schema = _ObjectSchema()
        
        for name, spec in service.get_process_parameter_specs().items():
            process_parameters_schema.add_property(name, {
                "type": spec["type"]
            },  spec.get("required", True))

        if not process_parameters_schema.has_properties():
            return False

        to_schema.add_property("parameters", process_parameters_schema.to_dict(), process_parameters_schema.has_required_properties())

        return True
    
    def build(self, service: mlservicewrapper.core.server.ServerInstance):

        service_info = service.get_info() or dict()

        info = {
            "title": service_info.get("name", "Hosted ML Service"),
            "version": service_info.get("version", "0.0.1")
        }

        batch_process_request_schema = _ObjectSchema()
        self._append_process_parameters_schema(batch_process_request_schema, service)
        self._append_datasets(batch_process_request_schema, "input", "inputs", service.get_input_dataset_specs())
        
        batch_process_response_schema = _ObjectSchema()
        self._append_datasets(batch_process_response_schema, "output", "outputs", service.get_output_dataset_specs())

        return{
            "swagger": "2.0",
            "info": info,
            "paths": {
                "/api/status": {
                    "get": {
                        "tags": [
                            "Service Health"
                        ],
                        "produces": ["application/json"],
                        "responses": {
                            "200": {
                                "description": "Returns the status of the model",
                                "schema": {
                                    "type": "object",
                                    "required": [
                                        "status",
                                        "ready"
                                    ],
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "title": "Model Status",
                                            "description": "A human-readable status message of the model load"
                                        },
                                        "ready": {
                                            "type": "boolean",
                                            "title": "Ready?",
                                            "description": "An indicator of whether the service is ready to accept requests"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/api/process/batch": {
                    "post": {
                        "tags": [
                            "Processing"
                        ],
                        "consumes": ["application/json"],
                        "parameters": [
                            {
                                "name": "request",
                                "in": "body",
                                "required": True,
                                "schema": batch_process_request_schema.to_dict()
                            }
                        ],
                        "produces": ["application/json"],
                        "responses": {
                            "200": {
                                "description": "Predicted results",
                                "schema": batch_process_response_schema.to_dict()
                            }
                        }
                    }
                }
            }
        }


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
        self._service: mlservicewrapper.core.server.ServerInstance or None = None
        self._load_error = False
        self._status_message = "Loading..."

    def is_ready(self):
        return self._service is not None and self._service.is_loaded()

    def on_stopping(self):
        if self._service is None:
            return

        self._service.dispose()

    def begin_loading(self):
        async def _do_load_async():
            try:
                self._service = mlservicewrapper.core.server.ServerInstance()

                print("load")
                await self._service.load()

                self._status_message = "Ready!"
            except:
                self._status_message = "Error during load!"
                raise
            finally:
                print("done load")

        def run():
            loop = asyncio.new_event_loop()
            c = _do_load_async()
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

            parameters = req_dict.get("parameters", dict())
            inputs = req_dict.get("inputs", dict())

            req_ctx = _HttpJsonProcessContext(parameters, inputs)

            logging.debug("parsed request body...")
        else:
            return _error_response(405, "This endpoint does not accept {}!".format(content_type))

        if not self.is_ready():
            return _error_response(503, "The model is still loading!")

        try:
            await self._service.process(req_ctx)
        except mlservicewrapper.core.errors.BadParameterError as err:
            return _bad_request_response(err.message, "parameter", err.name)
        except mlservicewrapper.core.errors.DatasetFieldError as err:
            return _bad_request_response(err.message, "dataset", err.name, {"field": err.field_name})
        except mlservicewrapper.core.errors.BadDatasetError as err:
            return _bad_request_response(err.message, "dataset", err.name)
        except mlservicewrapper.core.errors.BadRequestError as err:
            return _bad_request_response(err.message)

        outputs_dict = dict(((k, v.to_dict("records"))
                             for k, v in req_ctx.output_dataframes()))

        logging.debug("returning response...")

        return JSONResponse({
            "outputs": outputs_dict
        })

    def get_status(self, request: Request):

        return JSONResponse({
            "status": self._status_message,
            "ready": self.is_ready()
        }, 200)

    def get_swagger(self, request: Request):
        if self._service is None:
            return _error_response(503, "The service is not available!")

        swagger = _SwaggerBuilder().build(self._service)

        return JSONResponse(swagger, 200)

    def decorate_app(self, starlette_app: Starlette):
        api_prefix = "/api/"
        starlette_app.add_route(api_prefix + "status",
                                self.get_status, methods=["GET"])
        starlette_app.add_route(
            api_prefix + "process/batch", self.process_batch, methods=["POST"])

        starlette_app.add_route(
            "/swagger/v1/swagger.json", self.get_swagger, methods=["GET"])


_api = _ApiInstance()

application = Starlette(debug=True, on_startup=[
                        _api.begin_loading], on_shutdown=[_api.on_stopping])

_api.decorate_app(application)
