#!/usr/bin/env python3

import tarp.client

# Create a TARP client connected to the server running on localhost:8080
client = tarp.client.client('http://localhost:8080')

#The remote procedures are automatically discovered, so you can call them directly
result = client.my_function(1, 2)
print(result)  # Output: 3
