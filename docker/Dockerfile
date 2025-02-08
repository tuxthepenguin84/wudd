FROM ubuntu:noble
ARG DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y --no-install-recommends \
  apt-transport-https \
  build-essential \
  ca-certificates \
  git \
  python3 \
  python3-selenium \
  python3-requests \
  && update-ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /git/wudd
RUN git clone https://github.com/tuxthepenguin84/wudd.git /git/wudd
COPY /git/wudd/examples/win11.json /git/wudd/osinfo.json
VOLUME /git/wudd/downloads
VOLUME /git/wudd/outputs
VOLUME /git/wudd/osinfo.json
ENTRYPOINT ["/usr/bin/python3", "-u", "/git/wudd/wudd.py"]
CMD ["--download"]