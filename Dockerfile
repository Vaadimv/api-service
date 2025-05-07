FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libaio1 \
    unzip \
    gcc \
    libffi-dev \
    libssl-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копируем оба ZIP-файла
COPY instantclient-basic-linux.x64-23.7.0.25.01.zip /opt/oracle/
COPY instantclient-sdk-linux.x64-23.7.0.25.01.zip /opt/oracle/

# Распаковываем и настраиваем
RUN unzip -o /opt/oracle/instantclient-basic-linux.x64-23.7.0.25.01.zip -d /opt/oracle && \
    unzip -o /opt/oracle/instantclient-sdk-linux.x64-23.7.0.25.01.zip -d /opt/oracle && \
    rm /opt/oracle/*.zip && \
    ln -s /opt/oracle/instantclient_23_7 /opt/oracle/instantclient

# Переменные окружения
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient
ENV PATH=$LD_LIBRARY_PATH:$PATH

# Устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

