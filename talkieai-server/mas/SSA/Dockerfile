FROM python:3.10-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add source code and startup files
COPY . .
RUN chmod +x /app/start.sh

# Expose FastAPI port
EXPOSE 8000

# Use start.sh to control logging
ENTRYPOINT ["/app/start.sh"]
