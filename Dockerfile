# Lean image for the dashboard only (detection/training run on Colab or a GPU machine).
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[app]"

COPY config.yaml ./
COPY app ./app

# Mount your data at run time:  docker run -p 8501:8501 -v $(pwd)/data:/app/data pothole-monitor
EXPOSE 8501
CMD ["streamlit", "run", "app/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
