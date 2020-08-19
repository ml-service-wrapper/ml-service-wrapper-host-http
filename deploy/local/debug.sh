
if [ -z $SERVICE_CONFIG_PATH ]; then
    export SERVICE_CONFIG_PATH="../../../sample/1_simple/config.json"
fi

if [ -z $1 ]; then
    port="8000"
else
    port="$1"
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

cd $DIR

./setup.sh
./run.sh $port $SERVICE_CONFIG_PATH
