#!/usr/bin/env python3
import os

assert os.system("make") == 0

if __name__ == "__main__":
    os.execv("/data/openpilot/selfdrive/mapd/mapd.py", ['python3'])

