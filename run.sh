#!/bin/bash
source venv/bin/activate
python3 -m pidi --display st7789 --blur-album-art --rotation 270 $@
