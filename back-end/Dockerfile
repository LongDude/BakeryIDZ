# from python:3.12.8-alpine3.21
from surnet/alpine-python-wkhtmltopdf:3.13.0-0.12.6-small

WORKDIR /app/
COPY ./requirement.txt requirement.txt
RUN pip install -Ur requirement.txt

COPY . /app

CMD ["python", "app.py"]

