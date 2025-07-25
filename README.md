# README
**This software is of alpha status. It should not be used in any production code without the agreement and involvment of the authors.**

## TARP theory

TARP stands for "Tiny Asynchronous Remote Procedure" and is a framework for building small distributed applications in Python. It is desgined to be simple, lightweight and easy to use. It is NOT designed to be a full-features distributed system, and while it can use SSL for security it should NOT be used over the public internet without additional security measures. It is designed to be used in a trusted network environment, such as a local area network or a private cloud.

Quite often in academic programming one finds oneself in a situation where a program is artificially split over different physical machines. Sometimes the control for a device needs to run on windows, but the data needs to be processed on a linux machine, etc. etc. This split into multiple machines is not desirable, and you do not want to use a full distributed system to work around it. You want as thin a layer as possible to allow you to call functions on the remote machine as if they were local. TARP is designed to do just that. It allows you to call functions on a remote machine as if they were local, with minimal overhead and without the need for a full distributed system.

TARP provides three ways of connecting clients to servers:
1. **Synchronous RPC**: This is the simplest way to use TARP. You can call a function on the server and get the result back immediately. This is useful for small, quick operations that do not take a long time to complete. It uses Python pickles so will only work with a python client
2. **Asynchronous RPC**: This is similar to synchronous RPC, but it allows you to call a function on the server and get a handle back that you can use to check the status of the operation. This is useful for long-running operations that may take a while to complete. It also uses pickle and will only work with a python client.
3. **Web like interface**: Provides a wrapper around HTTP GET and POST requests, allowing you to call functions on the server using a mechanism more like a web API. This interface can be used from a browser, CURL/WGET or any other HTTP client.

## Simple TARP server

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

## Simple TARP client

The TARP client library should be placed in the code that you want to call remote procedures FROM. The TARP client can connect to a TARP server and call remote procedures. It is designed to be used in a trusted network environment, such as a local area network or a private cloud.

```python
import tarp.client

# Create a TARP client connected to the server running on localhost:8080
client = tarp.client.client('http://localhost:8080')

#The remote procedures are automatically discovered, so you can call them directly
result = client.my_function(1, 2)
print(result)  # Output: 3
```

If you put a docstring on the function on the server, then the client will automatically discover it and you can type `help(client.my_function)` to see the docstring. The paraneters and returns to and from the function are performed using Python pickles, so the client and server must be set up so that pickled objects can be sent between them. This means that the client and server must be running the same version of Python and have the same libraries installed. If you want to use TARP RPC with a different programming language, you will need to implement your own client library that can communicate with the TARP server using the same protocol.

## Asynchronous TARP server

Because TARP runs over HTTP/HTTPS, there is a maximum timeout for requests. If you want to run long-running operations, you can use the asynchronous TARP server. This allows you to call a function on the server and get a handle back that you can use to check the status of the operation.

```python
import tarp.server
# The procedure to be called remotely
def my_long_function(x, y):
    import time
    time.sleep(10)  # Simulate a long-running operation
    return x + y

# Create a TARP server prototype
server = tarp.server.makeServer()
# Register the function with the server
server.addAsyncRPCEndpoint('my_long_function', my_long_function)
# Start the server
tarp.server.runServer(server, port=8080)
```

By default, asynchronous RPC calls are run on the server in a separate process using multiprocessing to provide the maximum chance of actual parallelism. The downside is that you can't have global state since that is not duplicated across processes. If you want to use threads instead, you can pass `multiThreaded=True` to the `makeServer` function. This does mean that you can have global state, but the opportunities for parallelism are reduced due to the Python Global Interpreter Lock (GIL). Use the default multiprocessing unless you have a good reason not to. You can optionally add a `suggested_wait` parameter to the `addAsyncRPCEndpoint` method to suggest how long the client should wait before checking the status of the operation. This is just a suggestion and the client can ignore it.

## Asynchronous TARP client

Whether an endpoint is synchronous or asynchronous is determined by the server, so the client code does not change. You can call the asynchronous endpoint in the same way as the synchronous endpoint, but you will get a handle back that you can use to check the status of the operation.

```python
import tarp.client
# Create a TARP client connected to the server running on localhost:8080
client = tarp.client.client('http://localhost:8080')
# Call the asynchronous function
handle = client.my_long_function(1, 2)
result = handle.wait() # Wait for the result
print(result)  # Output: 3
```

If you want to check the status of the operation without waiting then you can use the 'status' method on the handle:

```python
status = handle.status() # Check the status of the operation
if status == 'in_progress':
    print('The operation is still in progress')
elif status == 'completed':
    print('The operation has completed')
elif status == 'failed':
    print('The operation has failed')
```

If you want to check the status of an operation and wait for one suggested wait wait time, you can use the `waitCycle` method. If the operation is still in progress then it will wait for the suggested wait time and return None. If the operation has completed or failed then it will return the result or raise an exception.

## Web-like interface server

The web-like interface server provides a way to call remote procedures using HTTP GET and POST requests. This allows you to call functions on the server using a mechanism more like a web API. The web-like interface can be used from a browser, CURL/WGET or any other HTTP client. The downside is that procedures now have to have a specific signature, first argument is a dict containing the query parameters (i.e. http://example.com/my_function?x=1&y=2 would return `{'x': 1, 'y': 2}`). They second argument is the body of the request. The type of this parameter is inferred from the MIME type of the request sent by the client. If the MIME type is `application/json` then the body is parsed as JSON, if it is `application/x-www-form-urlencoded` then it is converted to a dict mapping form key to value, and if it is `text/plain` then it is treated as plain text. Otherwise, and particularly if the MIME type is `application/octet-stream`, then the body is passed as a bytes object. Anything returned by the function is passed back to the client. If it is a dict or a list then it is converted to JSON and returned with the MIME type `application/json`. If it is a string then it is returned with the MIME type `text/plain`. If it is a bytes object then it is returned with the MIME type `application/octet-stream`.

By convention HTTP GET requests are used for read-only operations and all paramters are passed in the query string. POST requests are used for operations that change the state of the server, and all parameters are passed in the body of the request. Both query strings and message bodies are parsed as described above for both GET and POST requests for completeness.

```python
import tarp.server
# The procedure to be called remotely

lower=0
upper=10

#Function to set the lower and upper bounds for the sine wave plot
def set_params(params, body):
    global lower, upper
    if 'lower' in params:
        lower = float(params['lower'])
    if 'upper' in params:
        upper = float(params['upper'])
    return {'lower': lower, 'upper': upper}

# Function to generate data for a sine wave plot
def get_data(params, body):
    global lower, upper
    import numpy as np
    x = np.linspace(lower, upper, 100)
    y = np.sin(x)
    return {'x': x.tolist(), 'y': y.tolist()}

def get_plot(params, body):
    import matplotlib.pyplot as plt
    import numpy as np
    import io

    # get_data is still just a normal function
    result = get_data(params, body)
    x = np.array(result['x'])
    y = np.array(result['y'])

    global lower, upper
    plt.figure(figsize=(10, 5))
    plt.plot(x, y)
    plt.xlabel('x')
    plt.ylabel('sin(x)')
    plt.title('Sine Wave')
    plt.grid(True)
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return tarp.server.rawPayload(buf.getvalue(), mimetype='image/png')

# Create a TARP server prototype
server = tarp.server.makeServer()
# Register the functions with the server
server.addGetEndpoint('set_params', set_params)
server.addGetEndpoint('get_data', get_data)
server.addGetEndpoint('get_plot', get_plot)

# Start the server
tarp.server.runServer(server, port=8080)
```

This example has three endpoints: `set_params`, `get_data` and `get_plot`. The `set_params` endpoint allows you to set the lower and upper bounds for the sine wave plot, `get_data` returns the data for the sine wave plot as JSON, and the `get_plot` endpoint returns a PNG image of the sine wave plot. You can call these endpoints using a web browser or any HTTP client using the following URLs:
```
http://localhost:8080/set_params?lower=0&upper=3.14159
http://localhost:8080/get_data
http://localhost:8080/get_plot
```

`set_params` and `get_data` both return a JSON document which contains both the return values of the function and the success or failure of the call.
```json
{
    "status": "success",
    "result": {
        "x": [0.0, 0.1, 0.2, ...],
        "y": [0.0, 0.09983341664682815, 0.19866933079506122, ...]
    },
    "mimetype": "application/json"
}
```

or

```json
{
    "status": "error",
    "type": "type of the error",
    "message": "Error message describing what went wrong",
}
```
The `status` field indicates whether the operation was successful or not. If it was successful, the `result` field contains the result of the operation and the `mimetype` field indicates the MIME type of the result. If the operation failed, the `type` field indicates the type of error that occurred and the `message` field contains a description of the error.

The `get_plot` function returns an object of type `tarp.server.rawPayload`, which is a special type of payload that contains the raw bytes of the image and the MIME type of the image. This causes the server to not return the JSON document, but instead return the raw bytes of the image with the appropriate MIME type. The client can then display the image in a web browser or save it to a file. If you do not specify the MIME type, it defaults to `application/octet-stream`, which is a generic binary type and will cause most browsers to prompt the user to download the file rather than displaying it. If you get the mimetype wrong, the browser may not display the image correctly, so it is important to specify the correct MIME type.


## Web-like interface client

You can call web-like interfaces using any HTTP client, but the TARP client that you have already seen can also be used to call web-like interfaces. The TARP client will automatically detect the web-like interface and call the appropriate endpoint. To pass data to an endpoint as a query parameter, you pass it as a keyword argument to the method. To pass data to an endpoint as a body, you pass it as the first positional argument to the method. The TARP client will automatically convert the data to the appropriate format based on the type of the data.

```python
import tarp.client
# Create a TARP client connected to the server running on localhost:8080
client = tarp.client.client('http://localhost:8080')
# Set the lower and upper bounds for the sine wave plot
client.set_params(lower=0, upper=3.14159)

# Get the data for the sine wave plot
mimetype, data = client.get_data()
print(data)  # Output: {'x': [0.0, 0.1, 0.2, ...], 'y': [0.0, 0.09983341664682815, 0.19866933079506122, ...]}

# Get the sine wave plot as a PNG image
mimetype, plot = client.get_plot()
with open('sine_wave.png', 'wb') as f:
    f.write(plot)  # Save the image to a file

```

To call a method, simply call it by name on the client object. The return will be a tuple containing the MIME type of the response and the data returned by the server. If the method returns a `tarp.server.rawPayload` object, then the data will be the raw bytes of the payload. If it returns a JSON document, then the data will be a dict containing the result of the operation. If it is a text document, then the data will be a string containing the text. If a function on the remote end returned a binary object as a non rawPayload then the result will be the base64 encoded string of the binary data.

