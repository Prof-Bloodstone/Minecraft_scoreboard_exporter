FROM python:3.7-alpine

COPY requirements.txt /

RUN pip install -r requirements.txt

COPY mc_NBT_top_scores.py entrypoint.sh /

RUN chmod +x /mc_NBT_top_scores.py /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

