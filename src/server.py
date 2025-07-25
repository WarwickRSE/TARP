#   Copyright 2025 Chris Brady, Heather Ratcliffe
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
import ssl
import sys
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import time
import pickle
import base64
import concurrent.futures
import uuid

#Custom exception for "Operation in progress"
class OperationInProgress(Exception):
    def __init__(self, message="Operation not completed. Please wait.", retry_after=5):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)

#Custom exception for "Server is in invalid state"
class InvalidServerState(Exception):
    def __init__(self, message="Server is in an invalid state."):
        self.message = message
        super().__init__(self.message)

# Simple class to return an arbitrary payload
class rawPayload:
    def __init__(self, payload, mimetype = "auto"):
        self.payload = payload
        if mimetype == "auto":
            if isinstance(payload, bytes):
                self.mimetype = 'application/octet-stream'
            elif isinstance(payload, str):
                self.mimetype = 'text/plain'
            else:
                self.mimetype = 'application/json'
        else:
            self.mimetype = mimetype

    def __bytes__(self):
        return bytes(self.payload)
    
# Scan through a map for any byte objects. If they are found base64 encode them
def encode_bytes_in_map(data):
    """Recursively encodes byte objects in a dictionary or list to base64 strings."""
    if isinstance(data, dict):
        return {k: encode_bytes_in_map(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [encode_bytes_in_map(item) for item in data]
    elif isinstance(data, bytes):
        import base64
        return base64.b64encode(data).decode('utf-8')
    else:
        return data

def flatten_qs(qs):
    """Flattens a query string dictionary to a single level.
    If a key has multiple values, it returns a list of values.
    If a key has a single value, it returns the value directly.
    """
    return {k: v[0] if len(v) == 1 else v for k, v in qs.items()}
    
def api_success(result,mimetype):
    """Returns a JSON-encoded success response with the result and mimetype."""
    return json.dumps(encode_bytes_in_map({"status": "success", "mimetype": mimetype, "result": result})).encode('utf-8')

def api_error(message, type="generic"):
    """Returns a JSON-encoded error response with the message and type of error."""
    return json.dumps({"status": "error", "type":type, "message": message}).encode('utf-8')

#Create a multithreaded HTTP server that can handle multiple requests concurrently
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class server(BaseHTTPRequestHandler):

    get_endpoints = {} # Dictionary to hold GET endpoints
    post_endpoints = {} # Dictionary to hold POST endpoints
    rpc_endpoints = {} # Dictionary to hold RPC endpoints
    asyncRPC_endpoints = {} # Dictionary to hold AsyncRPC endpoints
    futures = {}  # Dictionary to hold futures for async RPC calls

    @classmethod
    def addGetEndpoint(cls, name, callback, result_mimetype=None, description=None, query_params=None):
        """Adds a GET endpoint to the server."""
        cls.get_endpoints[name] = {"func":callback, "mimetype":result_mimetype, "description": description or callback.__doc__ or "No description provided", "query_params":query_params}

    @classmethod
    def addPostEndpoint(cls, name, callback, result_mimetype=None, description=None, query_params=None, payload_mimetype=None, payload_schema=None):
        """Adds a POST endpoint to the server."""
        cls.post_endpoints[name] = {"func":callback, "mimetype":result_mimetype, "description": description or callback.__doc__ or "No description provided", "query_params":query_params, "payload_mimetype": payload_mimetype, "payload_schema": payload_schema}

    @classmethod
    def addRPCEndpoint(cls, name, callback, result_mimetype=None, description=None):
        """Adds an RPC endpoint to the server."""
        cls.rpc_endpoints[name] = {"func":callback, "mimetype":result_mimetype, "description": description or callback.__doc__ or "No description provided"}

    @classmethod
    def addAsyncRPCEndpoint(cls, name, callback, result_mimetype=None, description=None, suggested_wait=5):
        """Adds an AsyncRPC endpoint to the server."""
        cls.asyncRPC_endpoints[name] = {"func":callback, "mimetype":result_mimetype, "description": description or callback.__doc__ or "No description provided", "wait": suggested_wait}


    def get_known_endpoints(self):
        """ Returns a dictionary of known endpoints for both GET and POST methods.
        """
        endpoints = {}
        endpoints["GET"] = []
        endpoints["POST"] = []
        endpoints["RPC"] = []
        endpoints["ASYNCRPC"] = []
        for name, data in self.get_endpoints.items():
            endpoints["GET"].append({
                "name": name,
                "description": data['description'] or "No description provided",
                "query_params": data['query_params'] or []
            })
        for name, data in self.post_endpoints.items():
            endpoints["POST"].append({
                "name": name,
                "description": data['description'] or "No description provided",
                "query_params": data['query_params'] or [],
                "payload_mimetype": data['payload_mimetype'] or None,
                "payload_schema": data['payload_schema'] or None
            })
        for name, data in self.rpc_endpoints.items():
            endpoints["RPC"].append({
                "name": name,
                "description": data['description'] or "No description provided"
            })
        for name, data in self.asyncRPC_endpoints.items():
            endpoints["ASYNCRPC"].append({
                "name": name,
                "description": data['description'] or "No description provided"
            })
        return endpoints
    
    def handle_result(self, result, mimetype=None):
        """Handles the result returned by the endpoint.
        Depending on the type of result, it sets the appropriate response headers and writes the response body.
        """
        presult = result
        if isinstance(result, dict):
            mimetype = mimetype or 'application/json'
            presult = result
        elif isinstance(result, str):
            minetype = mimetype or 'text/plain'
            presult = result.encode('utf-8')
        elif isinstance(result, list):
            mimetype = mimetype or 'application/json'
            presult = result
        elif isinstance(result, rawPayload):
            #rawPayload class is used to return arbitrary payloads with a mimetype
            #Set the response headers based on the mimetype and doesn't wrap
            #the payload in the API result
            self.send_response(200)
            self.send_header('Content-Type', mimetype or result.mimetype)
            self.end_headers()
            self.wfile.write(bytes(result))
            return  # rawPayload is already written, no need to write again
        elif isinstance(result, bytes):
            # If the result is bytes, we assume it's binary data
            mimetype = mimetype or 'application/octet-stream'
            presult = result
        elif not result:
            presult = None
        else:
            #Payload is returned but is unrecognized. Bug so return 500
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(api_error('Unrecognized payload type').encode('utf-8'))
            return
        # Write the response body
        #Actual mimetype is always application/json because of API result format
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(api_success(presult, mimetype))

    def process_body(self, body_data, content_type):
        """Processes the body data based on the content type.
        If the content type is JSON, it parses the JSON data.
        If it's form-encoded, it parses the data as a query string.
        If it's plain text, it decodes the data.
        If it's binary data, it returns the raw bytes.
        If no content type is specified, it assumes raw bytes.
        """
        if content_type == 'application/json':
            try:
                return json.loads(body_data.decode('utf-8'))
            except json.JSONDecodeError:
                return body_data  # If JSON parsing fails, return raw bytes
        elif content_type == 'application/x-www-form-urlencoded':
            # Parse the body data as form-encoded
            return flatten_qs(parse_qs(body_data.decode('utf-8')))
        elif content_type == 'text/plain':
            # If it's plain text, we just decode it
            return body_data.decode('utf-8')
        elif content_type == 'application/octet-stream':
            # If it's binary data, we just return the raw bytes
            return body_data
        elif content_type is None:
            # If no content type is specified, we assume it's raw bytes
            return body_data
        else:
            # If the content type is not recognized, we just return the raw bytes
            return body_data
        
    def asyncGet(self):
        """Gets the result of an asynchronous operation by UUID."""
        query_params = parse_qs(urlparse(self.path).query)
        uuid = query_params.get('UUID', [None])[0]
        if not uuid:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(api_error('UUID parameter is required'))
            return
        if uuid not in self.futures:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(api_error('UUID not found').encode('utf-8'))
            return
        future = self.futures[uuid]['future']
        if future.done():
            result = future.result()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            result = {'payload': base64.b64encode(pickle.dumps(result)).decode('utf-8')}
            self.wfile.write(api_success(result, 'application/json'))
            del self.futures[uuid]
        else:
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Retry-After', str(self.futures[uuid]['wait']))
            self.end_headers()
            self.wfile.write(api_error("Operation still underway","OperationInProgress"))

    def asyncProbe(self):
        """Probes the status of an asynchronous operation by UUID."""
        query_params = parse_qs(urlparse(self.path).query)
        uuid = query_params.get('UUID', [None])[0]
        if not uuid:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(api_error('UUID parameter is required'))
            return
        if uuid not in self.futures:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(api_error('UUID not found').encode('utf-8'))
            return
        future = self.futures[uuid]['future']
        if future.done():
            result = future.result()
            status = 'completed'
        else:
            status = 'in_progress'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(api_success({'status': status, "suggested_wait":self.futures[uuid]['wait']}, 'application/json'))

    def do_GET(self):
        """Handles GET requests. This function is a core part of the HTTP server and
        is called whenever a GET request is made to the server."""
        parsed = urlparse(self.path)
        #Firt check if the path is root, if so call the get_endpoints
        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(api_success(self.get_known_endpoints(), 'application/json'))
            return
        #If the path is /asyncGet or /asyncProbe, handle those special cases
        if parsed.path == '/asyncGet':
            self.asyncGet()
            return
        if parsed.path == '/asyncProbe':
            self.asyncProbe()
            return

        # Otherwise, check if the path matches a registered endpoint
        endpoint = parsed.path.lstrip('/')
        if endpoint in self.get_endpoints:

            #Since RFC 7231 it is valid to have a GET request with a body, but it is not common. Still, we handle it gracefully and pass it to the endpoint if the endpoint has two parameters
            content_length = int(self.headers.get('Content-Length', 0))
            content_type = self.headers.get('Content-Type', None)
            body_data = self.rfile.read(content_length) if content_length else None
            body_data = self.process_body(body_data, content_type)
            try:
                result = self.get_endpoints[endpoint]['func'](flatten_qs(parse_qs(parsed.query)), body_data)
            except Exception as e:
                if isinstance(e, OperationInProgress):
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Retry-After', str(e.retry_after))
                    self.end_headers()
                    self.wfile.write(api_error(str(e),"OperationInProgress"))
                    return
                elif isinstance(e, InvalidServerState):
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(api_error(str(e),"InvalidServerState"))
                    return
                else:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(api_error(str(e)))
                    return
            self.handle_result(result, mimetype=self.get_endpoints[endpoint]['mimetype'])
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(api_error(str("Endpoint not found")))
            return


    def do_POST(self):
        """Handles POST requests. This function is a core part of the HTTP server and
        is called whenever a POST request is made to the server."""
        parsed = urlparse(self.path)
        endpoint = parsed.path.lstrip('/')
        if endpoint in self.rpc_endpoints:
            return self.do_RPC()
        if endpoint in self.asyncRPC_endpoints:
            return self.do_asyncRPC()
        if endpoint in self.post_endpoints:
            content_length = int(self.headers.get('Content-Length', 0))
            content_type = self.headers.get('Content-Type', None)
            body_data = self.rfile.read(content_length) if content_length else None
            body_data = self.process_body(body_data, content_type)
            try:
                result = self.post_endpoints[endpoint]['func'](flatten_qs(parse_qs(parsed.query)), body_data)
            except Exception as e:
                if isinstance(e, OperationInProgress):
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Retry-After', str(e.retry_after))
                    self.end_headers()
                    self.wfile.write(api_error(str(e)))
                    return
                elif isinstance(e, InvalidServerState):
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(api_error(str(e)))
                    return
                else:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(api_error(str(e)))
                    return
            self.handle_result(result, mimetype=self.post_endpoints[endpoint]['mimetype'])
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(api_error('Endpoint not found'))

    def do_RPC(self):
        """Handles RPC requests. This function is NOT part of the HTTP server and is
        called from do_POST when the path matches a registered RPC endpoint."""
        parsed = urlparse(self.path)
        endpoint = parsed.path.lstrip('/')
        if endpoint in self.rpc_endpoints:
            content_length = int(self.headers.get('Content-Length', 0))
            content_type = self.headers.get('Content-Type', None)
            body_data = self.rfile.read(content_length) if content_length else None
            body_data = self.process_body(body_data, content_type)
            #If there are any query parameters that is an error, #RPC endpoints should not have query parameters
            if parsed.query:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC endpoints should not have query parameters'))
                return
            #The body_data is a JSON object, with the top level being a dict with two keys: "args" and "kwargs"
            #If it isn't a dict at this point, it is an error
            if not isinstance(body_data, dict) or 'args' not in body_data or 'kwargs' not in body_data:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC body data should be a JSON object with "args" and "kwargs" keys'))
                return
            #The args and kwargs are base64 encoded pickles - unpack them
            args = pickle.loads(base64.b64decode(body_data['args']))
            kwargs = pickle.loads(base64.b64decode(body_data['kwargs']))
            if not isinstance(args, tuple):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC args should be a tuple'))
                return
            if not isinstance(kwargs, dict):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC kwargs should be a dict'))
                return
            try:
                result = {"payload":pickle.dumps(self.rpc_endpoints[endpoint]['func'](*args, **kwargs))}
            except Exception as e:
                if isinstance(e, OperationInProgress):
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Retry-After', str(e.retry_after))
                    self.end_headers()
                    self.wfile.write(api_error(str(e)))
                    return
                elif isinstance(e, InvalidServerState):
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(api_error(str(e)))
                    return
                else:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(api_error(str(e)))
                    return
            self.handle_result(result, mimetype=self.rpc_endpoints[endpoint]['mimetype'])
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(api_error('Endpoint not found'))

    def do_asyncRPC(self):
        """Handles AsyncRPC requests. This function is NOT part of the HTTP server and is
        called from do_POST when the path matches a registered AsyncRPC endpoint."""
        parsed = urlparse(self.path)
        endpoint = parsed.path.lstrip('/')
        if endpoint in self.asyncRPC_endpoints:
            content_length = int(self.headers.get('Content-Length', 0))
            content_type = self.headers.get('Content-Type', None)
            body_data = self.rfile.read(content_length) if content_length else None
            body_data = self.process_body(body_data, content_type)
            #If there are any query parameters that is an error, #RPC endpoints should not have query parameters
            if parsed.query:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC endpoints should not have query parameters'))
                return
            #The body_data is a JSON object, with the top level being a dict with two keys: "args" and "kwargs"
            #If it isn't a dict at this point, it is an error
            if not isinstance(body_data, dict) or 'args' not in body_data or 'kwargs' not in body_data:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC body data should be a JSON object with "args" and "kwargs" keys'))
                return
            #The args and kwargs are base64 encoded pickles - unpack them
            args = pickle.loads(base64.b64decode(body_data['args']))
            kwargs = pickle.loads(base64.b64decode(body_data['kwargs']))
            if not isinstance(args, tuple):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC args should be a tuple'))
                return
            if not isinstance(kwargs, dict):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(api_error('RPC kwargs should be a dict'))
                return
            #Run the async RPC function in a separate thread
            future = self.executor.submit(self.asyncRPC_endpoints[endpoint]['func'], *args, **kwargs)
            #Generate a UUID for the async operation
            ID = str(uuid.uuid4())
            self.futures[ID]={}
            self.futures[ID]['future'] = future
            self.futures[ID]['wait'] = self.asyncRPC_endpoints[endpoint].get('wait', 5)  # Default wait time is 5 seconds if not specified
            result = {"ID":ID, "suggested_wait": self.futures[ID].get('wait', 5)}

            self.handle_result(result, mimetype=self.asyncRPC_endpoints[endpoint]['mimetype'])
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(api_error('Endpoint not found'))

def runServer(cls, secure=False, certfile='snakeoil.pem', keyfile='snakeoil.key', port=None, bindTo=''):
    if secure:
        port = port or 443
    else:
        port = port or 80
    server_address = (bindTo, port)
    httpd = ThreadedHTTPServer(server_address, cls)
    if secure:
        httpd.socket = ssl.wrap_socket(
            httpd.socket,
            server_side=True,
            certfile=certfile,
            keyfile=keyfile,
            ssl_version=ssl.PROTOCOL_TLS
        )
        print(f'Serving HTTPS on port {port}')
    else:
        print(f'Serving HTTP on port {port}')
    httpd.serve_forever()

def makeServer(name='baseHandler', multiThreaded=False):
    sv = type(name,(server,),{})
    if multiThreaded:
        sv.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)  # Use a thread pool executor for multithreaded servers
    else:
        sv.executor = concurrent.futures.ProcessPoolExecutor(max_workers=10) # Use a process pool executor for single-threaded, multi process servers
    return sv