FROM python:3.12-slim

WORKDIR /app

# No generar .pyc (evita archivos de root en la carpeta montada) y salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Primero solo requirements: Docker reutiliza esta capa si no cambian las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
