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

import requests
import json
import time
import base64
import pickle

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

class client:

    class configInfo:
        """Configuration information for the client."""
        def __init__(self, client):
            object.__setattr__(self, 'client', client)
        
        #For any variable set in this, set the same named variable in the client
        def __getattr__(self, name):
            if name in self.client.remoteNames:
                raise AttributeError(f"{name} is a remote method, not a local attribute.")
            return getattr(self.client, name)
        
        def __setattr__(self, name, value):
            if name in self.client.remoteNames:
                raise AttributeError(f"{name} is a remote method, not a local attribute.")
            setattr(self.client, name, value)

    class asyncResult:
        """A class to represent an asynchronous function call."""
        def __init__(self, client, ID):
            self.client = client
            self.ID = ID
        
        def wait(self):
            """Wait for the asynchronous operation to complete."""
            return self.client.wait(self.ID)
        
        def probe(self):
            """Check the status of the asynchronous operation."""
            return self.client.probe(self.ID)
        
        def waitCycle(self):
            """Wait for the asynchronous operation to complete, checking status periodically."""
            pb = self.probe()
            if pb['status'] == 'in_progress':
                time.sleep(pb['suggested_wait'])
                return None
            elif pb['status'] == 'completed':
                return self.wait()
            elif pb['status'] == 'failed':
                raise Exception(f"Async operation failed with error: {pb.get('error', 'Unknown error')}")
        
        def status(self):
            result = self.probe()
            return result.get('status', 'unknown')

    def __init__(self, server_url, server_key=None):
        self.server_url = server_url.rstrip('/')
        self.server_key = server_key
        self.remoteNames = []
        self.loadEndpoints()
        self.config = self.configInfo(self)

    def checkAPIresult(self, response):
        """Check if the API response is successful."""
        if response.status_code == 404:
            raise Exception("API endpoint not found.")        
        if response.status_code != 200:
            #If the response is not 200 and the response is JSON, try to parse it
            try:
                json_response = response.json()
            except json.JSONDecodeError:
                raise Exception(f"API Error: {response.status_code} - {response.text}")            
            if (json_response.get('type',None) == 'OperationInProgress'):
                retry_after = int(response.headers.get('Retry-After', 5))
                raise OperationInProgress(json_response.get('message', 'Operation in progress'), retry_after=retry_after)
            elif (json_response.get('type',None) == 'InvalidServerState'):
                raise InvalidServerState(json_response.get('message', 'Invalid server state'))
            else:
                raise Exception(json_response.get('message', 'Unknown error'))
            
        #Now check the mime type. If it is not application/json have done all possible error checking, so return the result as binary1
        if response.headers.get('Content-Type') != 'application/json':
            return response.headers.get('Content-Type'), response.content
        json = response.json()
        if (json['status'] != 'success'):
            raise Exception(f"API Error: {json.get('message', 'Unknown error')}")
        return json.get('mimetype'), json.get('result', None)


    def loadEndpoints(self):
        """Fetch available endpoints from the control server."""
        resp = requests.get(f"{self.server_url}/", verify=self.server_key)
        mimetype, result = self.checkAPIresult(resp)
        posts = result.get('POST', [])
        gets = result.get('GET', [])
        rpcs = result.get('RPC', [])
        asyncRPCs = result.get('ASYNCRPC', [])

        #Now monkey patch the methods to this instance to match get endpoints
        #Methods take keyword arguments that are converted to query parameters
        for endpoint in gets:
            name = endpoint['name'].replace('/', '_')
            def get_method(name=name, **kwargs):
                params = '&'.join(f"{k}={v}" for k, v in kwargs.items())
                url = f"{self.server_url}/{name}?{params}"
                resp = requests.get(url, verify=self.server_key)
                return self.checkAPIresult(resp)
            self.__setattr__(name, get_method)
            self.remoteNames.append(name)
            #Now set the docstring to the endpoint description
            get_method.__doc__ = endpoint.get('description', f"GET method for {name}")
        #Now monkey patch the methods to this instance to match post endpoints
        for endpoint in posts:
            name = endpoint['name'].replace('/', '_')
            def post_method(payload=None, name=name, **kwargs):
                url = f"{self.server_url}/{name}"
                params = '&'.join(f"{k}={v}" for k, v in kwargs.items())
                if params:
                    url += f"?{params}"
                #Check the payload type and set the mimetype accordingly
                if payload:
                    if isinstance(payload, dict):
                        headers = {'Content-Type': 'application/json'}
                        payload = json.dumps(payload).encode('utf-8')
                    else:
                        headers = {'Content-Type': 'application/octet-stream'}
                    resp = requests.post(url, data=payload, headers=headers, verify=self.server_key)
                else :
                    resp = requests.post(url, verify=self.server_key)
                #Check the response and return the result
                return self.checkAPIresult(resp)                
            self.__setattr__(name, post_method)
            self.remoteNames.append(name)
            #Now set the docstring to the endpoint description
            post_method.__doc__ = endpoint.get('description', f"POST method for {name}")

        #Now monkey patch the methods to this instance to match rpc endpoints
        for endpoint in rpcs:
            name = endpoint['name'].replace('/', '_')
            def rpc_method(*args, name=name, **kwargs):
                url = f"{self.server_url}/{name}"
                #Prepare the payload as a JSON object with base64 encoded pickles
                payload = {
                    'args': base64.b64encode(pickle.dumps(args)).decode('utf-8'),
                    'kwargs': base64.b64encode(pickle.dumps(kwargs)).decode('utf-8')
                }
                headers = {'Content-Type': 'application/json'}
                resp = requests.post(url, data=json.dumps(payload).encode('utf-8'), headers=headers, verify=self.server_key)
                mime, results = self.checkAPIresult(resp)
                if mime != 'application/json':
                    raise Exception(f"RPC endpoint {name} returned non-JSON response: {mime}")
                #Unpack the results from base64 encoded pickles
                return pickle.loads(base64.b64decode(results['payload']))
            self.__setattr__(name, rpc_method)
            self.remoteNames.append(name)
            #Now set the docstring to the endpoint description
            rpc_method.__doc__ = endpoint.get('description', f"RPC method for {name}")

        #Now monkey patch the methods to this instance to match rpc endpoints
        for endpoint in asyncRPCs:
            name = endpoint['name'].replace('/', '_')
            def rpc_method(*args, name=name, **kwargs):
                url = f"{self.server_url}/{name}"
                #Prepare the payload as a JSON object with base64 encoded pickles
                payload = {
                    'args': base64.b64encode(pickle.dumps(args)).decode('utf-8'),
                    'kwargs': base64.b64encode(pickle.dumps(kwargs)).decode('utf-8')
                }
                headers = {'Content-Type': 'application/json'}
                resp = requests.post(url, data=json.dumps(payload).encode('utf-8'), headers=headers, verify=self.server_key)
                mime, results = self.checkAPIresult(resp)
                if mime != 'application/json':
                    raise Exception(f"RPC endpoint {name} returned non-JSON response: {mime}")
                #Unpack the results from base64 encoded pickles
                return self.asyncResult(self, results['ID'])
            self.__setattr__(name, rpc_method)
            self.remoteNames.append(name)
            #Now set the docstring to the endpoint description
            rpc_method.__doc__ = endpoint.get('description', f"Asynchronous RPC method for {name}")

    def getEndpoints(self):
        """Returns the list of available GET endpoints."""
        return [endpoint['name'] for endpoint in self.gets]
    
    def postEndpoints(self):
        """Returns the list of available POST endpoints."""
        return [endpoint['name'] for endpoint in self.posts]
    
    def wait(self, ID):
        """Wait for an asynchronous operation to complete."""
        url = f"{self.server_url}/asyncGet?UUID={ID}"
        while True:
            resp = requests.get(url, verify=self.server_key)
            try:
                mime, result = self.checkAPIresult(resp)
                if mime == 'application/json':
                    payload = pickle.loads(base64.b64decode(result['payload']))
                    return payload
                else:
                    raise Exception(f"Unexpected mimetype: {mime}")
            except OperationInProgress as e:
                time.sleep(e.retry_after)
                continue

    def probe(self, ID):
        """Check the status of an asynchronous operation."""
        url = f"{self.server_url}/asyncProbe?UUID={ID}"
        resp = requests.get(url, verify=self.server_key)
        mime, result = self.checkAPIresult(resp)
        if mime == 'application/json':
            return result
        else:
            raise Exception(f"Unexpected mimetype: {mime}")