FROM mcr.microsoft.com/playwright:focal

RUN apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
    python3-pip

COPY ./.devcontainer/requirements.prod.txt /tmp/requirements.txt
COPY ./deployments/docker-entrypoint.sh /

RUN pip install -r /tmp/requirements.txt && \
    playwright install && \
    rm /tmp/requirements.txt

COPY src /src

ENTRYPOINT ["/docker-entrypoint.sh"]
