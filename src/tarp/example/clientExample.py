#!/usr/bin/env python3
import tarp.client
import time
import sys
import argparse

#Parse the arguments for
# 1) Server URL
# 2) Server key (optional)
parser = argparse.ArgumentParser(description='Client for TARP server operations.')
parser.add_argument('--server-url', type=str, default="http://localhost:8080", help='URL of the TARP server (e.g., http://localhost:8080)')
parser.add_argument('--server-key', type=str, default=None, help='Optional server key for authentication')
args = parser.parse_args()

c = tarp.client.client(args.server_url, server_key=args.server_key)

# This is a non RPC call. It uses interfaces that are more like a web API
#and can be called easily from a web browser.
c.setRange(lower=0, upper=3.14159*1)
c.generateData()

#Long running operations can be polled for completion.
stillWaiting = True
while stillWaiting:
    try:
        mimetype, result = c.getData()
        if mimetype == 'application/json':
            print("Data received:")
            print(result)
            stillWaiting = False
        else:
            print(f"Unexpected mimetype: {mimetype}")
            break
    except tarp.client.OperationInProgress as e:
        retry_after = e.retry_after
        print(f"{e.message} Retrying in {retry_after} seconds...")
        time.sleep(retry_after)
    except tarp.client.InvalidServerState as e:
        print(e.message)
        break
    except Exception as e:
        print(f"Error: {e}")
        break

# You can return simple data like this - this returns an image directly
# as a PNG file. It can be viewed from the right endpoint in a web browser.
stillWaiting = True
while stillWaiting:
    # Show the generated figure
    try:
        mimetype, img_data = c.showFigure()
        if mimetype == 'image/png':
            with open('figure.png', 'wb') as f:
                f.write(img_data)
            print("Figure saved as figure.png")
            stillWaiting = False
        else:
            print(f"Unexpected mimetype for figure: {mimetype}")
            break
    except tarp.client.InvalidServerState as e:
        print(e.message)
    except tarp.client.OperationInProgress as e:
        print(f"{e.message} Retrying in {e.retry_after} seconds...")
        time.sleep(e.retry_after)
    except Exception as e:
        print(f"Error showing figure: {e}")