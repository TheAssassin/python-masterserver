FROM python:3.8-alpine

# dependency of coloredlogs it seems
RUN apk add --no-cache gcc g++ musl-dev libffi-dev cmake make py3-pybind11-dev git

WORKDIR /masterserver

VOLUME ["/data"]
CMD ["python", "-m", "masterserver", "/data/backup.txt"]

COPY masterserver/ /masterserver/masterserver/
COPY setup.py /masterserver/
COPY README.md /masterserver/

RUN pip install -e .[sentry]
