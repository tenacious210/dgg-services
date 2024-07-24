FROM python:3.11-alpine

WORKDIR /dgg-services-logger
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser -D appuser
RUN mkdir -p /dgg-services-logger/config && chown -R appuser:appuser /dgg-services-logger/config
USER appuser

ENTRYPOINT ["python", "logger.py"]