#! /usr/bin/env python3

import tarp.server

# The procedure to be called remotely
def my_function(x, y):
    return x + y

#Create a TARP server prototype
server = tarp.server.makeServer()

#Register the function with the server
server.addRPCEndpoint('my_function', my_function)

#Start the server
tarp.server.runServer(server, port=8080)
