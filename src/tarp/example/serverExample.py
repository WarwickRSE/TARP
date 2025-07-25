#!/usr/bin/env python3
import tarp.server
import matplotlib.pyplot as plt
import numpy as np
import io
import time
import sys

lower = 0
upper = 10
generatedFigure = False
stime = None
def setRange(query_params, payload):
    """Generates a range of numbers from lower to upper."""
    global lower, upper
    #Query parameters will be a dictionary with the content 
    #of whatever was called in the client call
    lower = float(query_params.get('lower', lower))
    upper = float(query_params.get('upper', upper))

#This would launch the long running operation and save a variable
#to indicate that an operation is underway
def generateData(query_params, payload):
    """Generates a figure based on query parameters."""
    global lower, upper, stime, generatedFigure, x, y
    x = np.linspace(lower, upper, 100)
    y = np.sin(x)
    generatedFigure = True
    stime = time.time()

def getData(query_params, payload):
    """Returns the generated data."""
    global x, y, stime, generatedFigure

    #If the data has not been generated then raise the special
    #exceptio (InvalidServerState) that indicates the server cannot return data at all
    if not generatedFigure:
        raise tarp.server.InvalidServerState("No figure generated yet. Call generateFigure first.")
    #If the operation is still in progress then raise the OperationInProgress exception
    if (time.time() - stime) < 10:
        raise tarp.server.OperationInProgress("Data is still being generated. Please wait a moment.", retry_after=10)
    #If the data is ready then return it as a JSON payload
    #This is a simple example, but you could return any data structure that can be serialized
    #to JSON, such as a list or dictionary.
    return {'x': x.tolist(), 'y': y.tolist()}

def showFigure(query_params, payload):
    """Displays the generated figure."""
    global img_buf, stime
    #Same approach as getData
    if not generatedFigure:
        raise tarp.server.InvalidServerState("No figure generated yet. Call generateFigure first.")
    if (time.time() - stime) < 10:
        raise tarp.server.OperationInProgress("Figure is still being generated. Please wait a moment.", retry_after=10)
    
    #This code is just generating an in memory image from matplotlib
    plt.figure()
    plt.plot(x, y)
    plt.title('Sine Wave')
    plt.xlabel('X-axis')
    plt.ylabel('Y-axis')
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png')
    img_buf.seek(0)
    plt.close()
    ### End of matplotlib code

    #Return the image data using the rawPayload type. The mime type should be 
    #an RFC 2045 compliant string, such as 'image/png' for PNG images.
    #This isn't essential for our client, but if you want to view the image in a web browser, it is necessary.
    return tarp.server.rawPayload(img_buf.getvalue(), mimetype='image/png')

#Used by RPCclientExample.py
def rpcExample(value,lower=0, upper=10):
    """An example RPC function that returns a value."""
    #This is now an RPC function. It can take any pickleable parameters either
    #as positional or keyword arguments. The server will automatically
    #parse the arguments and pass them to this function.

    #This function just waits for 10 seconds and then returns a range of numbers
    time.sleep(10)
    return np.linspace(lower,upper,value)

#Create the TARP server
server = tarp.server.makeServer()

# Register RPC endpoints
server.addRPCEndpoint('rpcExample', rpcExample)
#Suggested wait here is a guess for how often the client should poll for completion.
server.addAsyncRPCEndpoint('asyncRPCExample', rpcExample, suggested_wait=10)


# Register endpoints for HTML interface
server.addPostEndpoint('setRange', setRange)
server.addGetEndpoint('generateData', generateData)
server.addGetEndpoint('getData', getData)
server.addGetEndpoint('showFigure', showFigure)

#Parse the command line arguments for 
# 1) Secure connection (--secure)
# 2) Port number (--port)
# 3) Bind address (--bind)
# 4) Certificate and key files for secure connection
import argparse
parser = argparse.ArgumentParser(description='Run the TARP server with optional secure connection and port binding.')
parser.add_argument('--secure', action='store_true', help='Run server with secure connection (HTTPS)')
parser.add_argument('--port', type=int, default=8080, help='Port number to bind the server to (default: 8080)')
parser.add_argument('--bind', type=str, default='', help='Bind address for the server (default: all interfaces)')
parser.add_argument('--certfile', type=str, default='', help='Certificate file for secure connection (default: snakeoil.pem)')
parser.add_argument('--keyfile', type=str, default='', help='Key file for secure connection (default: snakeoil.key)')
args = parser.parse_args()

#Run the server that you just created
tarp.server.runServer(server, secure=args.secure,
                      certfile=args.certfile, keyfile=args.keyfile,
                      port=args.port, bindTo=args.bind)
