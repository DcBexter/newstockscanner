#!/bin/bash

(
cd backend || exit
python -m pytest --disable-socket --allow-unix-socket --cov --cov-branch --cov-report=xml
)
