FROM python:3.11-alpine

WORKDIR /dgg-services-manager
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup -g 997 docker
RUN adduser -D appuser && adduser appuser docker

RUN mkdir -p /dgg-services-manager/config && chown -R appuser:appuser /dgg-services-manager/config
USER appuser

ENTRYPOINT ["python", "dgg_services_manager.py"]