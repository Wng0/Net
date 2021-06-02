#!/usr/bin/env python3
# coding:utf-8
# python 入口模块
# win平台从vbs启动python
# unix平台从脚本shell启动python

import os
import sys
import time
import traceback
from datetime import datetime
import atexit

# 减少OpenWrt线程资源占用  
import threading
try:
    threading.stack_size(128*1024)
except:
    pass

try:
    import tracemalloc
    tracemalloc.start(10)
except:
    pass

current_path=os.path.dirname(os.path.abspath(__file__))
default_path=os.path.abspath(os.path.join(current_path,os.pardir))
data_path=os.path.abspath(os.path.join(default_path,os.pardir,os.pardir,'data'))
data_launcher_path=os.path.join(data_path,'launcher')
noarch_lib=os.path.abspath(os.path.join(default_path,'lib','noarch'))
sys.path.append(noarch_lib)
running_file=os.path.join(data_launcher_path,"Running.Lck")
data_gae_proxy_path=os.path.join(data_path,'gae_proxy')

# 为了及时更新,整个程序目录都会改变
# 但是用户自己的配置文件不可以改动
# 因此在程序目录的父目录建立用户数据目录

def creat_data_path():
    if not os.path.isdir(data_path):
        os.mkdir(data_path)
    if not os.path.isdir(data_launcher_path):
        os.mkdir(data_launcher_path)
    if not os.path.isdir(data_gae_proxy_path):
        os.mkdir(data_gae_proxy_path)

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