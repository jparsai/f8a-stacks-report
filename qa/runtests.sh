#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"

pushd "${SCRIPT_DIR}/.." > /dev/null

set -e
set -x

# test coverage threshold
COVERAGE_THRESHOLD=60

export TERM=xterm
TERM=${TERM:-xterm}

# set up terminal colors
NORMAL=$(tput sgr0)
RED=$(tput bold && tput setaf 1)
GREEN=$(tput bold && tput setaf 2)
YELLOW=$(tput bold && tput setaf 3)
F8A_UTIL_VERSION=e220735

printf "%sShutting down docker-compose ..." "${NORMAL}"

check_python_version() {
    python3 tools/check_python_version.py 3 6
}

gc() {
  retval=$?
  docker-compose -f ${SCRIPT_DIR}/../docker-compose.yml down -v || :
  rm -rf venv/
  exit $retval
}

trap gc EXIT SIGINT

check_python_version

function start_postgres {
    #pushd local-setup/
    echo "Invoke Docker Compose services"
    docker-compose -f docker-compose.yml up  -d
    #popd
}

start_postgres

function prepare_venv() {
    set +e
    VIRTUALENV="$(which virtualenv)"
    if [ $? -eq 1 ]; then
        echo "Trying to find virualenv-3"
        # python36 which is in CentOS does not have virtualenv binary
        VIRTUALENV="$(which virtualenv-3)"
    fi
    if [ $? -eq 1 ]; then
        echo "Virtualenv binary can't be found, using venv module instead"
        # still don't have virtual environment -> use python3 directly
        python3 -m venv venv && source venv/bin/activate
    else
        ${VIRTUALENV} -p python3 venv && source venv/bin/activate
    fi
    if [ $? -ne 0 ]
    then
        printf "%sPython virtual environment can't be initialized%s" "${RED}" "${NORMAL}"
        exit 1
    fi
    printf "%sPython virtual environment initialized%s\n" "${YELLOW}" "${NORMAL}"
    set -e
}
PYTHONPATH=$(pwd)/f8a_report/
export PYTHONPATH
export GENERATE_MANIFESTS="True"

export POSTGRESQL_USER='coreapi'
export POSTGRESQL_PASSWORD='coreapipostgres'
export POSTGRESQL_DATABASE='coreapi'
export PGBOUNCER_SERVICE_HOST='0.0.0.0'
export PGPORT="5432"
export REPORT_BUCKET_NAME="not-set"
export MANIFESTS_BUCKET="not-set"
export AWS_S3_ACCESS_KEY_ID="not-set"
export AWS_S3_SECRET_ACCESS_KEY="not-set"
export AWS_S3_REGION="not-set"

prepare_venv
pip3 install -r requirements.txt
pip3 install -r tests/requirements.txt
pip3 install git+https://github.com/fabric8-analytics/fabric8-analytics-utils.git@${F8A_UTIL_VERSION}
pip3 install git+https://git@github.com/fabric8-analytics/fabric8-analytics-version-comparator.git#egg=f8a_version_comparator
pip3 install "$(pwd)/."

python3 "$(which pytest)" -s --cov=f8a_report/ --cov-report term-missing --cov-fail-under=$COVERAGE_THRESHOLD -vv tests

codecov --token=d6bd6983-0bad-4eed-b8e3-9fd1d5199257
printf "%stests passed%s\n\n" "${GREEN}" "${NORMAL}"


popd > /dev/null
