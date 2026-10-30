FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "source360.api:app", "--host", "0.0.0.0", "--port", "8765"]
