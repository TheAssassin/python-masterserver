FROM python:3.8-alpine

# dependency of coloredlogs it seems
RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /masterserver

VOLUME ["/data"]
CMD ["python", "-m", "masterserver", "/data/data.zodb"]

COPY masterserver/ /masterserver/masterserver/
COPY setup.py  /masterserver/

RUN python setup.py develop
