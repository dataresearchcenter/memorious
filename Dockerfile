FROM python:3.13-slim

RUN apt-get -qq -y update \
    && apt-get -qq -y install python3-pil \
    # libxml2 libxslt \
    python3-pip libpq-dev python3-icu python3-psycopg2 \
    libicu-dev icu-devtools pkg-config \
    && apt-get -qq -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . /memorious
RUN pip3 install --no-cache-dir -e "/memorious[dev]"
WORKDIR /memorious

ENV MEMORIOUS_BASE_PATH=/data \
    MEMORIOUS_INCREMENTAL=true
