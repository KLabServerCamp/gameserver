#!/bin/bash

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get -y install --no-install-recommends bash-completion \
    default-mysql-client \
    vim

cp conf/.my.cnf conf/.dircolors ~/

python -m venv --prompt . .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

