FROM python:3

WORKDIR /usr/src/app

COPY server.py /usr/src/app/server.py
COPY engine.py /usr/src/app/engine.py
COPY sunfish.py /usr/src/app/sunfish.py
COPY tools/ /usr/src/app/tools
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "/usr/src/app/server.py" ]
