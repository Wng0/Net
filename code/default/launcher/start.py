#!/usr/bin/env python3
# coding:utf-8

import os
import sys
import time
import traceback
from datetime import datetime
import atexit

# 减少线程资源占用
import threading

current_path=os.path.dirname(os.path.abspath(__file__))

def creat_data_path():

creat_data_path()

from xlog import getlogger

def uncaughtExceptionHandler(etype, value, tb):

sys.excepthook=uncaughtExceptionHandler

has_desktop =True

def unload(module):

try:
    sys.path.insert(0,noarch_lib)

import sys_platform

def exit_handler():

atexit.register(exit_handler)

def main():

if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt: #control+C on console
        module_init.stop_all()
        os.exit(0)
        sys.exit()
    except Exception as e:
        xlog.exception("laucher except:%r",e)
        input ("Press Enter to continue...")