FROM python:3.12-slim
WORKDIR /app
COPY connect/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home relay && mkdir /state && chown relay:relay /state
COPY connect/relay.py connect/protocol.py ./
COPY connect/web ./web
COPY app/dist ./ui
COPY app/public/freedom.svg ./ui/freedom.svg
ENV PYTHONDONTWRITEBYTECODE=1 FREEDOM_CONNECT_ROOT=/app FREEDOM_CONNECT_STATE=/state FREEDOM_CONNECT_PORT=18869
USER relay
VOLUME ["/state"]
CMD ["python", "-B", "relay.py"]
