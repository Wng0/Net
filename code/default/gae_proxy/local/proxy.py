#!/usr/bin/env python2
# coding:utf-8
# Based on XX-Net 4.5.3
# Based on GAppProxy 2.0.0 by Du XiaoGang <dugang.2008@gmail.com>
# Based on WallProxy 0.4.0 by Hust Moon <www.ehust@gmail.com>
# 核心模块
import sys
import os
import traceback
import platform

current_path=os.path.dirname(os.path.abspath(__file__))
root_path=os.path.abspath(os.path.join(current_path,os.pathdir,os.pardir))
gae_proxy_path=os.path.join(root_path,"gae_proxy")
data_path=os.path.abspath(os.path.join(root_path,os.pardir,os.pardir,'data'))
data_gae_proxy_path=os.path.join(data_path,'gae_proxy')
python_path=root_path

noarch_lib=os.path.abspath(os.path.join(python_path,'lib','noarch'))
sys.path.append(noarch_lib)

if sys.platform=="win32":
    win32_lib=os.path.abspath(os.join(python_path,'lib','win32'))
    sys.path.append(win32_lib)
elif sys.platform.startswith("linux"):
    linux_lib=os.path.abspath(os.path.join(python_path,'lib','linux'))
    sys.path.append(linux_lib)

__file__=os.path.abspath(__file__)
if os.path.islink(__file__):
    __file__=getattr(os, 'readlink',lambda x:x)(__file__)
work_path=os.path.dirname(os.path.abspath(__file__))
os.chdir(work_path)

sys.path.append(root_path)
from gae_proxy.local.cert_util import CertUtil
from gae_proxy.local import proxy_handler
from gae_proxy.local.front import front, direct_front

def check_create_data_path():
    if not os.path.isdir(data_path):
        os.mkdir(data_path)
    if not os.path.isdir(data_gae_proxy_path):
        os.mkdir(data_gae_proxy_path)

from xlog import getLogger
xlog=getLogger("gae_proxy")
xlog.set_buffer(1000)

import simple_http_server
import env_info

proxy_server=None
# launcher/module_init will check this value for start/stop finished
ready=False

def log_info():
    xlog.info('-----------------------------------------------------')
    xlog.info('Python Version       :%s', platform.python_version())
    xlog.info('Os                   :%s', env_info.os_detail())
    xlog.info('Listen Address       :%s:%d', front.config.listen_ip, front.config.listen_port)
    if front.config.PROXY_ENABLE:
        xlog.info('%s Proxy     : %s:%s', front.config.PROXY_TYPE, front.config.PROXY_HOST,front.config.PROXY_PORT)
    if len(front.config.GAE_APPIDS):
        xlog.info('GAE APPID        :%s', '|'.join(front.config.GAE_APPIDS))
    else:
        xlog.info("Using public APPID")
    xlog.info('-----------------------------------------------------')

def main(args):
    global ready, proxy_server
    no_mess_system=args.get("no_mess_system",0)
    allow_remote=args.get("allow_remote",0)

    check_create_data_path()
    log_info()
    CertUtil.init_ca(no_mess_system)

    listen_ips=front.config.listen_ip
    if isinstance(listen_ips,str):
        listen_ips=[listen_ips]
    else:
        listen_ips=list(listen_ips)
    if allow_remote and ("0.0.0.0" not in listen_ips or "::" not in listen_ips):
        listen_ips=[(0.0.0.0),]
    addresses=[(listen_ip, front.config.listen_port) for listen_ip in listen_ips]
    #核心模块1
    front.start()
    direct_front.start()

    proxy_server=simple_http_server.HTTPServer(addresses, proxy_handler.GAEProxyHandler, logger=xlog)
    #checked by launcher.module_init
    ready=True
    proxy_server.server_forever()

#called by launcher/module/stop
def terminate():
    global ready, proxy_server
    xlog.info("start to terminate GAE_Proxy")
    ready=False
    front.stop()
    direct_front.stop()
    proxy_server.shutdown()

if __name__=='__main__':
    try:
        main({})
    except Exception:
        traceback.print_exc(file=sys.stdout)
    except KeyboardInterrupt:
        terminate()
        sys.exit()