FROM gitpod/workspace-mysql

USER gitpod
RUN sudo install-packages python3-pip

ENV PATH=$HOME/.pyenv/bin:$HOME/.pyenv/shims:$PATH
RUN pyenv update \
    && pyenv install 3.10.7 \
    && pyenv global 3.10.7 \
    && python3 -m pip install --no-cache-dir --upgrade pip

ENV PYTHONUSERBASE=/workspace/.pip-modules \
    PIP_USER=yes
ENV PATH=$PYTHONUSERBASE/bin:$PATH