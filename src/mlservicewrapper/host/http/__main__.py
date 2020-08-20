import argparse
import os

parser = argparse.ArgumentParser(description='Locally debug.', prog = "mlservicewrapper.core.debug")
parser.add_argument('--config', help='Path to service configuration file', required=False)
parser.add_argument('--host', help='Host to bind to', required=False, default="127.0.0.1")
parser.add_argument('--port', help='Port to bind to', required=False, default=5000, type=int)
parser.add_argument('--workers', help='How many workers to deploy', required=False, default=2, type=int)

parser.add_argument('--prod', help='Use production settings', action="store_true")

args = parser.parse_args()

if args.config:
    os.environ.setdefault("SERVICE_CONFIG_PATH", args.config)

os.sys.path.insert(0, os.path.dirname(__file__))

if args.prod:
    from .gunicorn_server import run_with_gunicorn
    run_with_gunicorn(args.host, args.port, args.workers)
else:
    import uvicorn
    uvicorn.run("server:app", host=args.host, port=args.port, log_level="trace")
