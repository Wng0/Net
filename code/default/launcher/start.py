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

# 为了及时更新,整个程序目录都会改变
# 但是用户自己的配置文件不可以改动
# 因此在程序目录的父目录建立用户数据目录

current_path=os.path.dirname(os.path.abspath(__file__))
default_path=os.path.abspath(os.path.join(current_path,os.pardir))
data_path=os.path.abspath(os.path.join(default_path,os.pardir,os.pardir,'data'))
data_launcher_path=os.path.join(data_path,'launcher')
noarch_lib=os.path.abspath(os.path.join(default_path,'lib','noarch'))
sys.path.append(noarch_lib)
running_file=os.path.join(data_launcher_path,"Running.Lck")
data_gae_proxy_path=os.path.join(data_path,'gae_proxy')

def creat_data_path():
    if not os.path.isdir(data_path):
        os.mkdir(data_path)
    if not os.path.isdir(data_launcher_path):
        os.mkdir(data_launcher_path)
    if not os.path.isdir(data_gae_proxy_path):
        os.mkdir(data_gae_proxy_path)

creat_data_path()

# 错误日志
from xlog import getLogger
log_file=os.path.join(data_launcher_path,"launcher.log")
xlog=getLogger("launcher",file_name=log_file)

def uncaughtExceptionHandler(etype, value, tb):
    if etype==KeyboardInterrupt: # Ctrl+C on console
        xlog.warn("Keyboard Interrrupt, exiting...")
        # 第一次出现的模块 module_init
        module_init.stop_all()
        os._exit(0)
    exc_info=''.join(traceback.format_exception(etype,value,tb))
    print(("uncaught Exception:\n"+exc_info))
    with open(os.path.join(data_launcher_path,"error.log"),"a") as fd:
        now=datetime.now()
        time_str=now.strftime("%b %d %H:%M:%S.%f")[:19]
        fd.write("%s type:%s traceback:%s" % (time_str,etype,value,exc_info))
    xlog.error("uncaught Exception, type=%s value=%s traceback:%s",etype, value, exc_info)
    # sys.exit(1)

sys.excepthook=uncaughtExceptionHandler

has_desktop =True

# 尝试引入OpenSSL

def unload(module):
    for m in list(sys.modules.keys()):
        if m==module or m.startswith(module + "."):
            del sys.modules[m]
    for p in list(sys.path_importer_cache.keys()):
        if module in p:
            del sys.path_importer_cache[p]
    try:
        del module
    except:
        pass

try:
    sys.path.insert(0,noarch_lib)
    import OpenSSL as oss_test
    xlog.info("use build-in openssl lib")
except Exception as e1:
    xlog.info("import build-in openssl fail:%r", e1)
    sys.path.pop(0)
    del sys.path_importer_cache[noarch_lib]
    unload("OpenSSL")
    unload("cryptography")
    unload("cffi")
    try:
        import OpenSSL
    except Exception as e2:
        xlog.exception("import system python-OpenSSL fail:%r", e2)
        print("Try install python-openssl\r\n")
        input("Press Enter to continue...")
        os._exit(0)


import sys_platform
from config import config
import web_control
import module_init
import update
import update_from_github
import download_modules

def exit_handler():
    print('Stopping all modules before exit!')
    module_init.stop_all()
    #出现的第2个模块
    web_control.stop()
    
atexit.register(exit_handler)

# main 函数 仅当自身调用时才会运行
def main():
    # change path to launcher
    global __file__
    __file__=os.path.abspath(__file__)
    if os.path.islink(__file__):
        __file__=getattr(os, 'readlink', lambda x:x)(__file__)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if sys.platform=="win32" and config.show_compat_suggest:
        import win_compat_suggest
        # 模块3
        win_compat_suggest.main()
    
    current_version = update_from_github.current_version()
    xlog.info("start XX-Net %s", current_version)
    web_control.confirm_xxnet_not_running()

    import post_update
    #模块4
    post_update.check()

    allow_remote=0
    no_mess_system=0
    if len(sys.argv) >1:
        for s in sys.argv[1:]:
            xlog.info("command args:%s",s)
            if s == "-allow_remote":
                allow_remote=1
            elif s== "-no_mess_system":
                no_mess_system=1
    if allow_remote or config.allow_remote_connect:
        xlog.info("start with allow remote connect.")
        #模块1第一次运行
        module_init.xargs["allow_remote"]=1
    if os.getenv("XXNET_NO_MESS_SYSTEM", "0")!="0" or no_mess_system or config.no_mess_system:
        xlog.info("start with no_mess_system, no CA will be imported to system.")
        module_init.xargs["no_mess_system"]=1
    if os.path.isfile(running_file):
        restart_from_except=True
    else:
        restart_from_except=False
    #模块1第2次运行
    module_init.start_all_auto()
    #模块2第1次运行
    web_control.start(allow_remote)

    if has_desktop and config.popup_webui==1 and not restart_from_except:
        host_port =config.control_port
        import webbrowser
        #模块5
        webbrowser.open("http://localhost:%s/" % host_port)
    #模块6
    update.start()
    if has_desktop:
        #模块7
        download_modules.start_dowload()
    #模块8
    update_from_github.cleanup()
    
    if config.show_systray:
        #模块9
        sys_platform.sys_tray.serve_forever()
    else:
        while True:
            time.sleep(1)

# main 函数 仅当自身调用时才会运行
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