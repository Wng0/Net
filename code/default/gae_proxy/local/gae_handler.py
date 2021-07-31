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

skip_request_headers = frozenset([b'Vary', b'Via', b'Proxy-Authorization', b'Proxy-Connection', b'Upgrade',b'X-Google-Cache-Control', b'X-Forwarded-For', b'X-Chrome-Variations',])
skip_response_headers = frozenset([b'Connection', b'Upgrade',b'Alt-Svc',b'Alternate-Protocol', b'X-Head-Content-Length',b'X-Google-Cache-Control', b'X-Chrome-Variations',]) #http://en.wikipedia.org/wiki/Chunked_transfer_encoding

def send_header(wfile,keyword,value):
    keyword = keyword.title()
    if keyword == b'Set-Cookie':
        # https://cloud.google.com/appenginge/docs/python/urlfetch/responseobjects
        for cookie in re.split(br',(?=[^ =]+(?:=|$))', value):
            wfile.write(b"%s: %s\s\r\n" % (keyword, cookie))
    elif keyword == b'Content-Disposition' and b'"' not in value:
        value = re.sub(br'filename=([^"\']+)', b'filename="\\1"', value)
        wfile.write(b"%s: %s\r\n" % (keyword, value))
    elif keyword in skip_response_headers:
        return
    else:
        if isinstance(value, int):
            wfile.write(b"%s: %d\r\n" % (keyword, value))
        else:
            wfile.write(b"%s: %s\r\n") % (keyword, value))

def send_response(wfile, status=404, headers={}, body=b''):
    body = utils.to_bytes(body)
    headers = dict((k.title(), v) for k, v in list(headers.item()))
    if b'Transfer-Encoding' in headers:
        del headers[b'Transfer-Encoding']
    if b'Content-Length' not in headers:
        headers[b'Content-Length'] = len(body)
    if b'Connection not in headers':
        headers[b'Connection'] = b'close'

    try:
        wfile.write(b"HTTP/1.1 %d\r\n" % status)
        for key, value in list(headers.items()):
            send_header(wfile,key, value)
        wfile.write(b"\r\n")
        wfile.write(body)
    except ConnectionAbortedError as e:
        xlog.warn("gae send response fail. %r",e)
        return
    except ConnectionResetError as e:
        xlog.warn("gae send response fail: %r",e)
        return
    except BrokenPipeError as e:
        xlog.warn("gae send response fail. %r",e)
        return
    except ssl.SSLError as e:
        xlog.warn("gae send response fail. %r", e)
        return
    except Exception as e:
        xlog.exception("send response fail %r", e)

def return_fail_message(wfile):
    html = generate_message_html('504 GAEProxy Proxy Time out', '连接超时,请先休息一下再来')
    send_response(wfile, 504, body = html.encode('utf-8'))
    return
    
def pack_request(method, url, headers, body, timeout):
    headers = dict(headers)
    if isinstance(body, bytes) and body:
        if len(body) <10 * 1024 * 1024 and b'Content-Encoding' not in headers:
            # 可以压缩
            zbody = deflate(body)
            if len(zbody)<len(body):
                body = zbody
                
