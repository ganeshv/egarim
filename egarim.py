# Lenovo Mirage camera API client over HTTP
# Before using this tool, you need to have generated the shared encryption key 
# using bluestrap.py

from mirage_api import *
import urllib.request
import sys
import os
import argparse
import ssl
import base64
import hmac

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def main(opts):

    if opts.subcommand == 'status':
        resp = simple_cmd(opts, status_request)
    elif opts.subcommand == 'get_capabilities':
        resp = simple_cmd(opts, get_capabilities_request)
    elif opts.subcommand == 'config_capture':
        resp = simple_cmd(opts, capture_config_request, active=opts.mode, rtmp_endpoint=opts.rtmp_endpoint,
           stream_name_key=opts.stream_name_key)
    elif opts.subcommand == 'start_capture':
        resp = simple_cmd(opts, start_capture_request, auto_stop=opts.auto_stop)
    elif opts.subcommand == 'stop_capture':
        resp = simple_cmd(opts, stop_capture_request)
    else:
        print('subcommand not implemented:', opts.subcommand)
        sys.exit(1)
    print(resp)

def sign(req, skey):
    h = hmac.new(skey, digestmod='sha256')
    h.update(req.method.encode('utf-8'))
    h.update(req.selector.encode('utf-8'))
    h.update(req.data)
    auth = base64.urlsafe_b64encode(h.digest()).decode('ascii')
    return auth
    
def simple_cmd(opts, request, **kwargs):
    with open(opts.skey, 'rb') as f:
        skey = f.read()

    headers = {
        'Content-Type': 'application/octet-stream'
    }
    r = request(**kwargs)
    if opts.debug:
        print('request', r)
    data = r.SerializeToString()
    req = urllib.request.Request('https://%s:%s/daydreamcamera' % (opts.host, opts.port), data=data, headers=headers, method='POST')
    signature = sign(req, skey)
    req.add_header('Authorization', 'daydreamcamera ' + signature)
    with urllib.request.urlopen(req, context=ctx) as f:
        data = f.read()
        return parse_response(data)

def process_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='camera hostname/IP', required=True)
    parser.add_argument('--port', help='camera https port', default=8443)
    parser.add_argument('--debug', help='verbose debugging', action='store_true')
    parser.add_argument('--skey', help='shared encryption key file', default='me_cam.skey')

    subparsers = parser.add_subparsers(dest='subcommand', title='Subcommands')

    subparsers.add_parser('status')
    subparsers.add_parser('get_capabilities')

    
    capture = subparsers.add_parser('config_capture')
    capture.add_argument('--mode', help='capture mode (video/photo/live)', choices=['video', 'photo', 'live'], default='photo')
    capture.add_argument('--rtmp_endpoint')
    capture.add_argument('--stream_name_key')


    start_capture = subparsers.add_parser('start_capture')
    start_capture.add_argument('--auto_stop', help='auto stop after x milliseconds', type=int)

    stop_capture = subparsers.add_parser('stop_capture')

    opts = parser.parse_args()
    if opts.subcommand is None:
        print(parser.print_help())
        sys.exit(1)

    if not os.path.exists(opts.skey):
        print('%s doesn\'t exist; pair using btmirage.py to generate the shared encryption key' % (opts.skey,))
        sys.exit(1)

    return opts

if __name__ == '__main__':
    n = process_args()
    main(n)
