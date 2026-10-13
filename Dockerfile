FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_ENV=production
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_ENV=local DJANGO_SECRET_KEY=build-only-static-assets EMAIL_ADDRESS= EMAIL_HOST_PASSWORD= python manage.py collectstatic --noinput \
    && useradd --uid 10001 --create-home oy \
    && mkdir -p /app/private_media \
    && chown -R oy:oy /app
USER oy
EXPOSE 8000
ENTRYPOINT ["sh", "/app/deployment/entrypoint.sh"]
CMD ["gunicorn", "bulk_delivery_project.wsgi:application", "--config", "gunicorn.conf.py"]
