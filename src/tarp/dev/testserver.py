from sys import argv

import tarp.server

if(len(argv) > 1):
  #Assuming port
  try:
    port = int(argv[1])
  except:
    print("Invalid port specified: " + argv[1]+"\n Falling back to 8080")
    port = 8080
else:
  port = 8080


# The procedure to be called remotely
def my_function(x, y):
    return x + y

#Create a TARP server prototype
server = tarp.server.makeServer()

#Register the function with the server
server.addRPCEndpoint('my_function', my_function)

#Start the server
tarp.server.runServer(server, port=port)

