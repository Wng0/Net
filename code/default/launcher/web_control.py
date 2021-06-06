#!/user/bin/env python
# coding:utf-8
# 第一个核心网络控制模块
import os
import sys

current_path=os.path.dirname(os.path.abspath(__file__))
if __name__=="__main__":
    python_path=os.path.abspath(os.path.join(current_path,os.pardir))
    noarch_lib=os.path.abspath(os.path.join(python_path,'lib','noarch'))
    sys.path.append(noarch_lib)

import re
import socket, ssl
import urllib.parse
import urllib.request, urllib.error, urllib.parse
import time
import threading

root_path=os.path.abspath(os.path.join(current_path, os.pardir))

import json
import cgi

import sys_platform
import xlog import getLogger
xlog=getLogger("launcher")
import module_init
from config import config
import autorun
import update
import update_from_github
import simple_http_client
import simple_http_server
import utils
from simple_i18n import SimpleI18N

NetWorkIOError=(socket.error, ssl.SSLError, OSError)
i18_translator=SimpleI18N(config.lauguage)

module_menus={}
class Http_Handler(simple_http_server.HttpServerHandler):
    deploy_proc=None
    def load_module_menus(self):
        global module_menus
        new_module_menus={}
        modules=config.all_modules
        for module in modules:
            if getattr(config, "enable_"+ module)!=1:
                continue
            menu_path=os.path.join(root_path, module, "web_ui", "menu.json") #Laucher & gae_proxy modules
            if not os.path.isfile(menu_path):
                continue
            #i18n code lines (Both the Local dir and the template dir are module dependent)
            local_dir = os.path.abspath(os.path.join(root_path,module, 'lang'))
            stream=i18n_translator.render(local_dir, menu_path)
            module_menu=json.loads(utils.to_str(stream))
            new_module_menus[module]=module_menu
        module_menus=sorted(iter(new_module_menus.items()), key=lambda k_and_v: (k_and_v[1]['menu_sort_id']))

    def do_POST(self):
        self.headers=utils.to_str(self.headers)
        self.path=utils.to_str(self.path)
        refer=self.headers.get('Referer')
        if refer:
            refer_loc=urllib.parse.urlparse(refer).netloc
            host=self.headers.get('Host')
            if refer_loc!=host:
                xlog.warn("web contrl ref:%s host:%s", refer_loc, host)
                return
        try:
            ctype, pdict=cgi.parse_header(self.headers.get('Content-Type',""))
            if ctype=='multipart/ form-data':
                self.postvars=cgi.parse_multipart(self.rfile, pdict)
            elif ctype=='application/ x-www-form--urlencoded':
                length=int(self.headers.get('Content-Length'))
                self.postvars=urllib.parse.parse_qs(self.rfile.read(length),keep_blank_values=True)
            else:
                self.postvars={}
        except Exception as e:
            xlog.exception("do_POST %s except:%r", self.path, e)
            self.postvars={}

        url_path_list=self.path.split('/')
        if len(url_path_list)>=3 and url_path_list[1]=="module":
            module=url_path_list[2]
            if len(url_path_list)>=4 and url_path_list[3]== "control":
                if module not in module_init.pro_handler:
                    xlog.warn("request %s no module in path",self.path)
                    return self.send_not_found()
                path='/'+'/'.join(url_path_list[4:])
                controler=module_init.proc_handler[module]["imp"].local.web_control.ControlHandler


