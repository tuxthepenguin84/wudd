FROM python:3.14-slim AS builder

ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PATH="/opt/venv/bin:$PATH"

WORKDIR /git/wudd

RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir --upgrade pip

COPY requirements.txt ./
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .
RUN cp examples/win11.toml osinfo.toml

FROM python:3.14-slim

ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PATH="/opt/venv/bin:$PATH"

WORKDIR /git/wudd

RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  chromium \
  chromium-driver \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /git/wudd /git/wudd

VOLUME /git/wudd/downloads
VOLUME /git/wudd/outputs

ENTRYPOINT ["/opt/venv/bin/python", "-u", "/git/wudd/wudd.py"]
CMD ["--download"]
