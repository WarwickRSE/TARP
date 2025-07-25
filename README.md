# README
**This software is of alpha status. It should not be used in any production code without the agreement and involvment of the authors.**

## TARP theory

TARP stands for "Tiny Asynchronous Remote Procedure" and is a framework for building small distributed applications in Python. It is desgined to be simple, lightweight and easy to use. It is NOT designed to be a full-features distributed system, and while it can use SSL for security it should NOT be used over the public internet without additional security measures. It is designed to be used in a trusted network environment, such as a local area network or a private cloud.

TARP provides three ways of connecting clients to servers:
1. **Synchronous RPC**: This is the simplest way to use TARP. You can call a function on the server and get the result back immediately. This is useful for small, quick operations that do not take a long time to complete. It uses Python pickles so will only work with a python client
2. **Asynchronous RPC**: This is similar to synchronous RPC, but it allows you to call a function on the server and get a handle back that you can use to check the status of the operation. This is useful for long-running operations that may take a while to complete. It also uses pickle and will only work with a python client.
3. **Web like interface**: Provides a wrapper around HTTP GET and POST requests, allowing you to call functions on the server using a mechanism more like a web API. This interface can be used from a browser, CURL/WGET or any other HTTP client.

## TARP server

The TARP server library should be placed in the code that you want to call remote procedures ON. The TARP server can handle multiple simultaneous clients, but it is strongly recommended that you do not use it for more than a few clients at a time. It is designed to be used in a trusted network environment, such as a local area network or a private cloud.

```python
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
```

This creates a TARP server running on port 8080 that can be accessed by clients. The `my_function` can be called by clients using the TARP client library. By default TARP binds to all network interfaces, but you can specify a specific interface by passing a suitable IP string to the `bindTo` parameter of `runServer`.

## TARP client

The TARP client library should be placed in the code that you want to call remote procedures FROM. The TARP client can connect to a TARP server and call remote procedures. It is designed to be used in a trusted network environment, such as a local area network or a private cloud.

```python
import tarp.client

# Create a TARP client connected to the server running on localhost:8080
client = tarp.client.client('http://localhost:8080')

#The remote procedures are automatically discovered, so you can call them directly
result = client.my_function(1, 2)
print(result)  # Output: 3
```