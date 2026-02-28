#!/bin/bash

lxterminal --working-directory=/home/pi/roberta/openroberta-lab \
  --command="bash -c './ora.sh start-from-git; exec bash'" &

sleep 1

lxterminal --working-directory=/home/pi/roberta/qiskit_wifi_api.py \
  --command="bash -c 'source /home/pi/roberta/qiskit_wifi_api.py/.venv/bin/activate; python /home/pi/roberta/qiskit_wifi_api.py/qiskit_wifi_api.py; exec bash'" &