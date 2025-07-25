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
print("About to call a synchronous RPC example. Should take about 10 seconds.")
print(c.rpcExample(15, lower=0, upper=100))
print("That was a synchronous RPC example. So long as the response is less than a few seconds, it will work as expected.")
l = c.asyncRPCExample(15, lower=0, upper=10)
print("\n\n\n")

#You could just call l.wait() here and it would block until execution completes, but this is an example of how to use the probe method to check the status of the async operation.
print(f"Async RPC Example started with UUID: {l.ID}")
pb = l.probe()
print(pb)
while(pb['status'] == 'in_progress'):
    print(f"Async RPC Example still in progress. Status: {pb['status']}. Retrying in {pb['suggested_wait']} seconds.")
    time.sleep(pb['suggested_wait'])
    pb = l.probe()
print(f"Async RPC Example completed with status: {pb['status']}. Result: {l.wait()}")

sys.exit(0)
