#!/usr/bin/env bash

VENV=.venv-$(uname -m)

if [ ! -d "$VENV" ]; then
  python3 -m venv $VENV
fi

. $VENV/bin/activate

# python3 server.py --host 0.0.0.0 --port 4567 --key meingeheimespasswort
python3 server.py --host 0.0.0.0 --port 4567 
