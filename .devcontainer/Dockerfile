FROM mcr.microsoft.com/devcontainers/base:ubuntu

# [Optional] Uncomment this section to install additional OS packages.
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get -y install --no-install-recommends bash-completion \
        default-libmysqlclient-dev default-mysql-client default-mysql-server \
        vim
