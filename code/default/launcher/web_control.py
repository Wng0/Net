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
from xlog import getLogger
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
i18n_translator=SimpleI18N(config.lauguage)

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
            
            #Laucher & gae_proxy modules
            menu_path=os.path.join(root_path, module, "web_ui", "menu.json") 
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
                controler=module_init.proc_handler[module]["imp"].local.web_control.ControlHandler(self.client_address, self.headers, self.command, path, self.rfile, self.wfile)
                controler.postvars=utils.to_str(self.postvars)
                return controler.do_POST()
        
        self.send_not_found()
        xlog.info('%s "%s %s HTTP/1.1" 404 - ',self.address_string(), self.command, self.path)

    def do_GET(self):
        self.headers=utils.to_str(self.headers)
        self.path=utils.to_str(self.path)

        refer=self.headers.get('Referer')
        if refer:
            refer_loc=urlib.parse.urlparse(refer).netloc
            host=self.headers.get('Host')
            if refer_loc !=host:
                xlog.warn("web control ref:%s host:%s",refer_loc, host)
                return
        # check for "..", which will leak file
        if re.search(r'(\.{2})',self.path) is not None:
            self.wfile.write(b'HTTP/1.1 404\r\n\r\n')
            xlog.warn('%s %s %s  haking', self.address_string(), self.command, self.path)
            return
        
        url_path=urllib.parse.urlparse(self.path).path
        if url_path=='/':
            return self.req_index_handler()
        
        url_path_list = self.path.split('/')
        if len(url_path_list)>=3 and url_path_list[1]=="module":
            module=url_path_list[2]
            if len(url_path_list)>=4 and url_path_list[3]=="control":
                if module not in module_init.proc_handler:
                    x.log.warn ("request %s no module in path", url_path)
                    self.send_not_found()
                    return

                if "imp" not in module_init.proc_handler[module]:
                    xlog.warn("request module:%s start fail", module)
                    self.send_not_found()
                    return
                
                path = '/'+'/'.join(url_path_list[4])
                controler=module_init.proc_handler[module]["imp"].local.web_control.ControlHandler(self.client_address, self.headers, self.command, path, sefl.rfile, self.wfile)
                controler.do_GET()
                return
            else:
                relate_path = '/'.join(url_path_list[3:])
                file_path =os.path.join(root_path, module, "web_ui", relate_path)
                if not os.path.isfile(file_path):
                    return self.send_not_found()

                #i18n code lines (Both the Local dir and the template dir are module dependent)
                locale_dir=os.path.abspath(os.path.join(root_path, module, 'lang'))
                content=i18n_translator.render(locale_dir,file_path)
                return self.send_response('text/html', content)
        else:
            file_path=os.path.join(current_path, 'web_ui'+url_path)
        
        if os.path.isfile(file_path):
            if file_path.endswith('.js'):
                mimetype='application/javascript'
            elif file_path.endswith('.css'):
                mimetype='text/css'
            elif file_path.endswith('.html'):
                mimetype='text/html'
            elif file_path.endswith('.jpg'):
                mimetype='image/jpeg'
            elif file_path.endswith('.png'):
                mimetype='image/png'                
            else:
                mimetype='text/plain'
            self.send_file(file_path, mimetype)
        else:
            xlog.debug('launcher web_control %s %s %s ', self.address_string(), self.command, self.path)
            if url_path=='/config':
                self.req_config_handler()
            elif url_path=='/update':
                self.req_update_handler()
            elif url_path=='/config_proxy':
                self.req_config_proxy_handler()
            elif url_path=='/init_module':
                self.req_init_module_handler()
            elif url_path=='/quit':
                self.send_response('text/html','{"status":"success"}')
                sys_platform.sys_tray.on_quit(None)
            elif url_path=="/debug":
                self.req_debug_handler()
            elif url_path=='/restart':
                self.send_response('text/html','{"status":"success"}')
                update_from_github.restart_xxnet()
            else:
                self.send_not_found()
                xlog.info('%s "%s %s HTTP/1.1" 404 -', self.address_string(), self.command, self.path)
    
    def req_index_handler(self):
        req=urllib.parse.urlparse(self.path).query
        reqs=urllib.parse.parse_qs(req, keep_blank_values=True)

        try:
            target_module=reqs['module'][0]
            target_menu=reqs['menu'][0]
        except:
            if config.enable_x_tunnel:
                target_module='x_tunnel'
                target_menu='config'
            #elif config.get(['modules', 'smart_router', 'auto_start'],0)==1:
            elif config.enable_gae_proxy:
                target_module='gae_proxy'
                target_menu='status'
            else:
                target_module='laucher'
                target_menu='about'
        
        if len(module_menus)==0:
            self.load_module_menus()
        
        # i18n code lines
        locale_dir= os.path.abspath(os.path.join(current_path,'lang'))
        index_content=i18n_translator.render(local_dir,os.path.join(current_path, "web_ui", "index.html"))

        current_version=utils.to_bytes(update_from_github.current_version())
        menu_content=b''
        for module, v in module_menus:
            title=v["module_title"]
            menu_content+=b'<li class="nav-header">%s</li>\n' % utils.to_bytes(title)
            for sub_id in v ['sub_menus']:
                sub_title =v['sub_menus'][sub_id]['title']
                sub_url=v['sub_menus'][sub_id]['url']
                if target_module==module and target_menu==sub_url:
                    active=b'class="active"'
                else:
                    active=b''
                menu_content+=b'<li %s><a href="/?module=%s&menu=%s">%s</a></li>\n' % utils.to_bytes(active, module, sub_url, sub_title))
        right_content_file=os.path.join(root_path, target_module,"web_ui", target_menu+".html")
        if os.path.isfile(right_content_file):
            locale_dir=os.path.abspath(os.path.join(root_path, target_module, 'lang'))
            right_content=i18n_translator.render(locale_dir, os.path.join(root_path, target_module, "web_ui", target_menu+".html"))
        else:
            right_content=b""
        
        data=index_content % (current_version,current_version,menu_content,right_content)
        self.send_response('text/html',data)
    
    def req_config_handler(self):



                

