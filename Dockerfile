FROM python:3.7-alpine

RUN apk add --update \
    bash \
    busybox-suid \
    && rm -rf /var/cache/apk/*

ENV CRON_USER=minecraft

RUN addgroup -S $CRON_USER && adduser -S $CRON_USER -G $CRON_USER

COPY --chown=$CRON_USER:$CRON_USER requirements.txt /

RUN pip install -r requirements.txt

COPY --chown=$CRON_USER:$CRON_USER mc_NBT_top_scores.py entrypoint.sh /

RUN chmod +x /mc_NBT_top_scores.py /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

