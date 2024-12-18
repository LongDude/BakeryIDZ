from python:3.12.8-alpine3.21

WORKDIR /app/
COPY ./requirement.txt requirement.txt
RUN pip install -Ur requirement.txt

COPY . /app

CMD ["python", "app.py"]

