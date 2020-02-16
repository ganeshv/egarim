import datetime
from camera_api_pb2 import *
import subprocess
import io

JMIRAGE = "java -cp . MirageCrypto "
counter = 2000

# The camera uses \x00\x00 as an end-of-message marker for Bluetooth messages.
# These need to be escaped and encoded/decoded before applying encryption/decryption.

def mm_encode(msg):
    out = b''
    for i in range(len(msg)):
        if i > 0 and msg[i - 1] == 0 and (msg[i] == 0 or msg[i] == 1):
            out += b'\x01'
        out += msg[i:i+1]
    out += b'\x00\x00'
    return out

def mm_decode(msg):
    if len(msg) < 2 or msg[-1] != 0 or msg[-2] != 0:
        raise Exception('no EOM marker found')
    out = b''
    for i in range(len(msg) - 2):
        if i > 0 and msg[i - 1] == 0 and msg[i] == 1:
            continue
        out += msg[i:i+1]
    return out

# Bluetooth messages (other than key initiate/finalize) are encrypted by the shared key

def encrypt(msg, key):
    return subprocess.check_output(JMIRAGE + " encrypt " + key, input=msg, shell=True)

def decrypt(msg, key):
    return subprocess.check_output(JMIRAGE + " decrypt " + key, input=msg, shell=True)

# Generate shared key from the ECDH public key of the camera + our key
def genshared(me, cam):
    return subprocess.check_output(JMIRAGE + " genshared %s %s " % (me, cam), shell=True)

# Generate our ECDH key
def genkey(me):
    return subprocess.check_output(JMIRAGE + " genkey %s" % (me,), shell=True)

def new_request():
    global counter
    counter = counter + 1
    req = CameraApiRequest()    
    req.header.expiration_timestamp = int((datetime.datetime.timestamp(datetime.datetime.now()) + 40000) * 1000)
    req.header.request_id = counter
    return req

def wifi_config_request(ssid=None, password=None):
    if ssid is None or password is None:
        raise Exception('ssid and password must be set')
    req = new_request()
    req.type = CameraApiRequest.CONFIGURE
    req.configuration_request.local_wifi_info.ssid = ssid
    req.configuration_request.local_wifi_info.password = password
    return req

def time_config_request(tz='Europe/London'):
    req = new_request()
    req.type = CameraApiRequest.CONFIGURE
    req.configuration_request.time_configuration.timestamp = int(datetime.datetime.now().replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    req.configuration_request.time_configuration.timezone = tz
    return req

def capture_config_request(active=None, rtmp_endpoint=None, stream_name_key=None):
    modes = {
        'live': CaptureMode.LIVE,
        'photo': CaptureMode.PHOTO,
        'video': CaptureMode.VIDEO
    }
    req = new_request()
    req.type = CameraApiRequest.CONFIGURE
    if active:
        req.configuration_request.capture_mode.active_capture_type = modes[active]
    if rtmp_endpoint:
        req.configuration_request.capture_mode.configured_live_mode.rtmp_endpoint = rtmp_endpoint
    if stream_name_key:
        req.configuration_request.capture_mode.configured_live_mode.stream_name_key = stream_name_key
    return req

def start_capture_request(auto_stop=None):
    req = new_request()
    req.type = CameraApiRequest.START_CAPTURE
    if auto_stop:
        req.start_capture_request.auto_stop_duration_ms = auto_stop
    return req

def stop_capture_request():
    req = new_request()
    req.type = CameraApiRequest.STOP_CAPTURE
    return req

def get_capabilities_request():
    req = new_request()
    req.type = CameraApiRequest.GET_CAPABILITIES
    return req

def status_request():
    req = new_request()
    req.type = CameraApiRequest.STATUS
    return req

def factory_reset_request():
    req = new_request()
    req.type = CameraApiRequest.FACTORY_RESET
    return req

def key_init(name, mode='initiate'):
    with open(name + '.pub', mode='rb') as f:
        pk = f.read()
    with open(name + '.salt', mode='rb') as f:
        salt = f.read()

    req = CameraApiRequest()    
    req.type = CameraApiRequest.KEY_EXCHANGE_INITIATE \
        if mode == 'initiate' else CameraApiRequest.KEY_EXCHANGE_FINALIZE

    req.key_exchange_request.public_key = pk
    req.key_exchange_request.salt = salt

    return req

def key_response(resp, peer_name):
    if resp.response_status.status_code == CameraApiResponse.ResponseStatus.OK:
        with open(peer_name + '.pub', mode='wb') as f:
            f.write(resp.key_exchange_response.public_key)
        with open(peer_name + '.salt', mode='wb') as f:
            f.write(resp.key_exchange_response.salt)
        return True
    return False

def finalize_response(resp):
    return resp.response_status.status_code == CameraApiResponse.ResponseStatus.OK

def parse_response(data):
    resp = CameraApiResponse()
    resp.ParseFromString(data)
    return resp

def key_finalize(name):
    return key_init(name, mode='finalize')
