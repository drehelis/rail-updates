FROM mcr.microsoft.com/playwright:focal

RUN apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
    python3-pip

COPY requirements.dev.txt /tmp/
RUN pip install -r /tmp/requirements.dev.txt

COPY requirements.prod.txt /tmp/
RUN pip install -r /tmp/requirements.prod.txt

RUN playwright install
