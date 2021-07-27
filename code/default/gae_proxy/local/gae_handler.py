#!/usr/bin/env/ python
# coding:utf-8
"""
Go Agent local-server protocol 3.2

request:
POST /_gh/ HTTP/1.1
HOST: appid.appspot.com
content-length: xxx

http content:
body
{
    pack_req_head_len: 2 byte, #post 时使用
    pack_req_head: deflate{ 此为负载
        original request line
        original request headers,
        X-URLFETCH-kwargs HEADS, {
            password,
            maxsize, defined in config AUTO RANGE MAX SIZE
            timeout, request timeout for GAE urlfetch.
        }
    }
    body
}
response:
200 OK
http-Heads:
Content-type: image/gif
headers from real_server
# real_server 为gae让客户以为的服务器
# 可能被gae改变,但对客户端不可见
# 未分片body也直接发给客户端
# body 分为下面两个部分
http-content:{
    response_head{
        data_len:  2 byte,
        data: deflate{
            HTTP/1.1 status, status_code headers
            content = error_message, if GAE server fail  
        }
    }
    body
}
"""
import errno
import time
import xstruct as struct
import re
import string
import ssl
import urllib.parse
import threading
import zlib
import traceback
from mimetypes import guess_type
from . import check_local_network
from .front import front
import utils
from xlog import getLogger
xlog = getLogger("gae_proxy")

def inflate(data):
    return zlib.decompress(data, -zlib.MAX_WBITS)

def deflate(data):
    return zlib.compress(data)[2:-4]

class GAE_Exception(Exception):
    def __init__(self, error_code, message):
        xlog.debug("GAE_Exception %r %r", error_code, message)
        self.error_code = error_code
        self.message = "%r:%s" % (error_code, message)
    
    def __str__(self):
        # for %s
        return repr(self.message)
    
    def __repr__(self):
        # for %r
        return repr(self.message)

def generate_message_html(title, banner, detail=''):
    MESSAGE_TEMPLATE = '''
    <html><head>
    <meta http-equiv="content-type" content="text/html;charset=utf-8">
    <title>$title</title>
    <style><!--
    body {font-family: arial,sans-serif}
    div.nav {margin-top: 1ex}
    div.nav A {font-size: 10pt; font-family: arial,sans-serif}
    span.nav {font-size: 10pt; font-family: arial,sans-serif; font-weight: bold}
    div.nav A,span.big {font-size: 12pt; color: #0000cc}
    div.nav A {font-size: 10pt; color: black}
    A.l:link {color: #6f6f6f}
    A.u:link {color: green}
    //--></style>
    </head>
    <body text=#000000 bgcolor=#ffffff>
    <table border=0 cellpadding=2 cellspacing=0 width=100%>
    <tr><td bgcolor=#3366cc><font face=arial,sans-serif color=#ffffff><b>Message</b></td></tr>
    <tr><td> </td></tr></table>
    <blockquote>
    <H1>$banner</H1>
    $detail
    <p>
    </blockquote>
    <table width=100% cellpadding=0 cellspacing=0><tr><td bgcolor=#3366cc><img alt="" width=1 height=4></td></tr></table>
    </body></html>
    '''
    return string.Template(MESSAGE_TEMPLATE).substitute(title = title, banner = banner, detail = detail)

def spawn_later(seconds, target, *args, **kwargs):
    def wrap(*args, **kwargs):
        __import__('time').sleep(seconds)
        try:
            result = target(*args, **kwargs)
        except BaseException:
            result = None
        return result
    return __import__('thread').start_new_thread(wrap,args,kwargs)

skip_request_headers = frozenset([b'Vary', b'Via', b'Proxy-Authorization'])

