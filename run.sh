#!/bin/sh
source venv/bin/activate
trap 'kill $pid1 $pid2' 2
python3 application.py &
pid1=$!
python3 application.py &
pid2=$!
wait
