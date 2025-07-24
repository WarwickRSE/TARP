import requests
import json
import time

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

    def __init__(self, server_url, server_key=None):
        self.server_url = server_url.rstrip('/')
        self.server_key = server_key
        self.remoteNames = []
        self.loadEndpoints()
        self.config = self.configInfo(self)

    def checkAPIresult(self, response):
        print (f"Checking API response: {response.status_code} {response.reason}")
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
                raise Exception()
            
        #Now check the mime type. If it is not application/json have done all possible error checking, so return the result as binary
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

        #Now monkey patch the methods to this instance to match get endpoints
        #Methods take keyword arguments that are converted to query parameters
        for endpoint in gets:
            name = endpoint['name'].replace('/', '_')
            def get_method(name=name, **kwargs):
                params = '&'.join(f"{k}={v}" for k, v in kwargs.items())
                url = f"{self.server_url}/{name}?{params}"
                resp = requests.get(url)
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
                print(f"Posting to {url} with payload: {payload}")
                #Check the payload type and set the mimetype accordingly
                if payload:
                    if isinstance(payload, dict):
                        headers = {'Content-Type': 'application/json'}
                        payload = json.dumps(payload).encode('utf-8')
                    else:
                        headers = {'Content-Type': 'application/octet-stream'}
                    resp = requests.post(url, data=payload, headers=headers)
                else :
                    resp = requests.post(url)
                #Check the response and return the result
                return self.checkAPIresult(resp)                
            self.__setattr__(name, post_method)
            self.remoteNames.append(name)
            #Now set the docstring to the endpoint description
            post_method.__doc__ = endpoint.get('description', f"POST method for {name}")

        def getEndpoints():
            """Returns the list of available GET endpoints."""
            return [endpoint['name'] for endpoint in gets]
        
        def postEndpoints():
            """Returns the list of available POST endpoints."""
            return [endpoint['name'] for endpoint in posts]