DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

cd $DIR/../../..

pythonExecutable="python3"

apt install python3-pip
apt install gunicorn

apt install gunicorn

$pythonExecutable -m pip install ./src/core
$pythonExecutable -m pip install -r "./src/http_api/requirements.txt"
$pythonExecutable -m pip install uvicorn gunicorn
