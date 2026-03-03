#!/usr/bin/env bash

VENV=.venv-$(uname -m)

if [ ! -d "$VENV" ]; then
  python3 -m venv $VENV
fi

. $VENV/bin/activate


