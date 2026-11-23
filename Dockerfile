FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY manage.py .
COPY config/ config/
COPY meets/ meets/
RUN python manage.py collectstatic --noinput && useradd --system --uid 10001 nongkee && mkdir /data && chown nongkee /data
ENV DJANGO_ENV=production NONGKEE_DB=/data/nongkee.sqlite3
USER nongkee
EXPOSE 8000
CMD ["sh", "-ec", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 --access-logfile -"]

