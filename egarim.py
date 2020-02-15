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

    subparsers = parser.add_subparsers(dest='subcommand', title='Subcommands')

    parser_status = subparsers.add_parser('status')
    parser_status.add_argument('--skey', help='shared encryption key file', default='me_cam.skey')

    
    opts = parser.parse_args()
    if opts.subcommand is None:
        print(parser.print_help())
        sys.exit(1)

    if hasattr(opts, 'skey') and not os.path.exists(opts.skey):
        print('%s doesn't exist; pair using btmirage.py to generate the shared encryption key' % (opts.skey,))
        sys.exit(1)

    return opts

if __name__ == '__main__':
    n = process_args()
    main(n)
