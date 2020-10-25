#!/bin/bash

set -e
virtualenv -p /usr/bin/python3 venv
source venv/bin/activate

pip3 install --requirement requirements.txt


python3 ./setup.py install
