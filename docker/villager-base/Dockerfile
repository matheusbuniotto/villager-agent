FROM golang:1.24-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Astral uv — single static binary, no Python build tools needed
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

ENV PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"

WORKDIR /workspace
