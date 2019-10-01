FROM python:3.7-alpine

ADD requirements.txt ./

RUN pip install -r requirements.txt

ADD mc_NBT_top_scores.py ./

CMD ["python3", "-u", "mc_NBT_top_scores.py"]
