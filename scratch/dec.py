from camera_api_pb2 import *
import sys

r = CameraApiResponse() if sys.argv[1] == 'resp' else CameraApiRequest()
r.ParseFromString(bytes.fromhex(sys.argv[2]))
print(r)

