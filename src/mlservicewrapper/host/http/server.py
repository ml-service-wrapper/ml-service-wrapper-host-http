import asyncio
import logging
import threading
import typing

import pandas as pd
from mlservicewrapper.core import (configuration, context_sources, contexts,
                                   errors, server, services)
from pandas.core import base
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


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
    def _append_datasets(self, to_schema: _ObjectSchema, direction: str, field: str, specs: typing.Iterable[configuration.DatasetSchema]):

        datasets_schema = _ObjectSchema()

        for spec in specs:
            if spec.item_schema is None:
                continue

            datasets_schema.add_property(spec.name, {
                "type": "array",
                "title": f"{spec.name} {direction} dataset",
                "items": spec.item_schema
            }, spec.required)

        if not datasets_schema.has_properties():
            return False

        to_schema.add_property(field, datasets_schema.to_dict(), datasets_schema.has_required_properties())

        return True

    def _append_process_parameters_schema(self, to_schema: _ObjectSchema, service: server.ServerInstance):

        process_parameters_schema = _ObjectSchema()

        for spec in service.get_process_parameter_specs().items():
            process_parameters_schema.add_property(spec.name, {
                "type": spec.type
            },  spec.required)

        if not process_parameters_schema.has_properties():
            return False

        to_schema.add_property("parameters", process_parameters_schema.to_dict(), process_parameters_schema.has_required_properties())

        return True

    def build(self, service: server.ServerInstance, base_path: str = None):

        service_info = service.get_info()

        info = {
            "title": service_info.name or "Hosted ML Service",
            "version": service_info.version or "0.0.1"
        }

        batch_process_request_schema = _ObjectSchema()
        self._append_process_parameters_schema(batch_process_request_schema, service)
        self._append_datasets(batch_process_request_schema, "input", "inputs", service.get_input_dataset_specs())

        batch_process_response_schema = _ObjectSchema()
        self._append_datasets(batch_process_response_schema, "output", "outputs", service.get_output_dataset_specs())

        if not base_path:
            base_path = "/"
        elif not base_path.endswith("/"):
            base_path = base_path + "/"

        paths = dict()

        paths[base_path + "api/status"] = {
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
        }

        paths[base_path + "api/process/batch"] = {
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

        ret = {
            "swagger": "2.0",
            "info": info
        }

        ret["paths"] = paths

        return ret


class _HttpJsonProcessContextSource(context_sources.CollectingProcessContextSource):
    def __init__(self, parameters: dict, inputs: dict):
        super().__init__()
        self.__parameters = parameters or dict()
        self.__inputs = inputs or dict()

    def get_parameter_value(self, name: str, required: bool = True, default: str = None) -> str:
        context_sources.NameValidator.raise_if_invalid(name)

        if name in self.__parameters:
            return self.__parameters[name]

        if required and default is None:
            raise errors.MissingParameterError(name)

        return default

    async def get_input_dataframe(self, name: str, required: bool = True):
        if name in self.__inputs:
            return pd.DataFrame.from_records(self.__inputs[name])

        if required:
            raise errors.MissingDatasetError(name)

        return None

def _get_url_path(*parts: typing.List[str]):
    def _trim(part: str):
        if part.startswith("/"):
            part = part[1:]

        if part.endswith("/"):
            part = part[:-1]

        return part

    trimmed = (_trim(p) for p in parts)
    with_len = (pt for pt in trimmed if len(pt) > 0)

    return "/" + "/".join(with_len)

class _ApiInstance:
    def __init__(self):
        self._service = server.ServerInstance("http")
        
        http_config = self._service.build_load_context()

        base_path: str = http_config.get_parameter_value("BasePath", default="/")

        if not base_path.startswith("/"):
            raise ValueError("basePath must begin with a leading slash!")

        print(f"Hosting with base path '{base_path}'")
        http_config.logger.info("Hosting with base path: '%s'", base_path)

        self._base_path = base_path
        
        self._load_error = False
        self._status_message = "Loading..."

    def is_ready(self):
        return self._service.is_loaded()

    def on_stopping(self):
        self._service.dispose()

    def begin_loading(self):
        async def _do_load_async():
            try:
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
            req_dict: dict = await request.json()

            parameters = req_dict.get("parameters", dict())
            inputs = req_dict.get("inputs", dict())

            req_ctx = _HttpJsonProcessContextSource(parameters, inputs)
        else:
            return _error_response(405, "This endpoint does not accept {}!".format(content_type))

        if not self.is_ready():
            return _error_response(503, "The model is still loading!")

        try:
            await self._service.process(req_ctx)
        except errors.BadParameterError as err:
            return _bad_request_response(err.message, "parameter", err.name)
        except errors.DatasetFieldError as err:
            return _bad_request_response(err.message, "dataset", err.name, {"field": err.field_name})
        except errors.BadDatasetError as err:
            return _bad_request_response(err.message, "dataset", err.name)
        except errors.BadRequestError as err:
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
        swagger = _SwaggerBuilder().build(self._service, base_path=self._base_path)

        return JSONResponse(swagger, 200)

    def decorate_app(self, starlette_app: Starlette):
        starlette_app.add_route(_get_url_path(self._base_path, "api", "status"), self.get_status, methods=["GET"])
        starlette_app.add_route(_get_url_path(self._base_path, "api", "process", "batch"), self.process_batch, methods=["POST"])

        starlette_app.add_route(_get_url_path(self._base_path, "swagger", "v1", "swagger.json"), self.get_swagger, methods=["GET"])


_api = _ApiInstance()

application = Starlette(debug=True,
                        on_startup=[_api.begin_loading],
                        on_shutdown=[_api.on_stopping])

_api.decorate_app(application)
