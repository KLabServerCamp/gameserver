#!/bin/bash

python -m venv --prompt . venv
venv/bin/pip install -U pip
venv/bin/pip install -r requirements.txt

cp conf/.my.cnf conf/.dircolors ~/
