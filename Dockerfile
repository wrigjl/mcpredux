FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENTRYPOINT ["python", "-u", "server.py"]
CMD ["--mode", "http", "--host", "0.0.0.0"]
