FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN sed -i '/^torch==/d' requirements.txt && \
    pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]