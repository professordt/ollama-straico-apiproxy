FROM python:3.12-alpine

WORKDIR /app

# Install aio-straico from GitHub first
RUN pip install --no-cache-dir git+https://github.com/jayrinaldime/aio-straico.git

# Install other dependencies
RUN pip install --no-cache-dir fastapi uvicorn langfuse<3.0.0 httpx python-multipart jinja2 aiocache

COPY . /app

# Create agent data directory
RUN mkdir -p /app/data/agent

EXPOSE 3214

HEALTHCHECK --interval=1m --timeout=10s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3214/docs || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3214"]
