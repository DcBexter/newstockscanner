#!/bin/bash

(
cd backend || exit
python -m pytest --cov --cov-branch --cov-report=xml
)
