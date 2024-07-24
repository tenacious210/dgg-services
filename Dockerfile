FROM python:3.11-alpine

WORKDIR /dgg-services-logger
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup -g 997 docker
RUN adduser -D appuser && adduser appuser docker

RUN mkdir -p /dgg-services-logger/config && chown -R appuser:appuser /dgg-services-logger/config
USER appuser

ENTRYPOINT ["python", "logger.py"]