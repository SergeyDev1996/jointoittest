FROM python:3.11

WORKDIR /app

COPY . /app

RUN pip install -r requirements.txt

# launcher.py MUST be PID 1 for signal handling to work correctly
ENTRYPOINT ["python", "launcher.py"]
