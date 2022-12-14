# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.192.0/containers/python-3/.devcontainer/base.Dockerfile

#ARG VARIANT="3.10"
#FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

FROM mcr.microsoft.com/devcontainers/base:ubuntu

# [Optional] Uncomment this section to install additional OS packages.
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get -y install --no-install-recommends bash-completion \
        default-libmysqlclient-dev default-mysql-client default-mysql-server \
        vim
