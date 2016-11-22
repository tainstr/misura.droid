#!/bin/bash

T=`readlink -m "${BASH_SOURCE[0]}"`
ROOT="$( cd "$( dirname "${T}" )"/../.. && pwd )"
export PYTHONPATH=$ROOT:$PYTHONPATH
