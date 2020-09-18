import argparse
import os
import uvicorn

parser = argparse.ArgumentParser(description='Locally debug.', prog = "mlservicewrapper.core.debug")
parser.add_argument('--config', help='Path to service configuration file', required=False)
parser.add_argument('--host', help="Host to bind to", required=False, default="127.0.0.1")
parser.add_argument('--port', help="Port to bind to", required=False, default=5000, type=int)

args = parser.parse_args()

if args.config:
    os.environ.setdefault("SERVICE_CONFIG_PATH", args.config)

os.sys.path.insert(0, os.path.dirname(__file__))

uvicorn.run("server:application", host=args.host, port=args.port, log_level="trace")
