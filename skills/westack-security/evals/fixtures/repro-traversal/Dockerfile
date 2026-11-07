# FIXTURE for westack-security's reproduction mode. Build and run only under the user's grant naming both:
#   docker build -t westack-repro-traversal .            (pulls python:3.12-slim: network, under the grant)
#   docker run --rm --network none --read-only westack-repro-traversal
FROM python:3.12-slim
WORKDIR /app
COPY app.py repro.py secret.txt ./
COPY public ./public
USER 65534
CMD ["python", "-B", "repro.py"]
