FROM brewblox/rpi-python:3.7 as base

COPY ./dist /app/dist
RUN pip3 install wheel \
    && pip3 wheel /app/dist/* --wheel-dir=/wheeley --find-links=/wheeley


FROM brewblox/rpi-python:3.7-slim

EXPOSE 5000
WORKDIR /app

COPY --from=base /wheeley /wheeley

RUN ls /wheeley \
    && pip3 install --no-index --find-links=/wheeley brewblox-flasher \
    && rm -rf /wheeley \
    && pip3 freeze

ENTRYPOINT ["python3", "-m", "brewblox_flasher"]
