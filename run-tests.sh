#!/bin/bash
cd backend
python -m pytest --cov --cov-branch --cov-report=xml
cd ..
