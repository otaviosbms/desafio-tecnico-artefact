FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Migra, carrega os CSVs (idempotente) e sobe o servidor.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py load_data && python manage.py runserver 0.0.0.0:8000"]
