if [ -z $1 ]; then
    echo "Please specify a port to bind!"
    exit 1
fi

if [ -z $SERVICE_CONFIG_PATH ]; then
    if [ -z $2 ]; then
        echo "Please specify a config file to use!"
        exit 1
    fi

    SERVICE_CONFIG_PATH=$2
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

export SERVICE_CONFIG_PATH=`readlink -f $SERVICE_CONFIG_PATH`

echo "Using config file: $SERVICE_CONFIG_PATH"

cd $DIR/../../../src/http_api

gunicorn -b 0.0.0.0:$1 main:app -k uvicorn.workers.UvicornWorker
