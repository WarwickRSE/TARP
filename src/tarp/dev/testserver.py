from sys import argv
import platform

import tarp.server

def describe_host():
  vals = {}
  vals['hostname'] = platform.node()
  vals['system'] = platform.system()
  vals['arch'] = platform.machine()
  vals['proc'] = platform.processor()

  return vals

# The procedure to be called remotely
def my_function(x, y):
    return x + y

def server():

  if(len(argv) > 1):
    #Assuming port
    try:
      port = int(argv[1])
    except:
      print("Invalid port specified: " + argv[1]+"\n Falling back to 8080")
      port = 8080
  else:
    port = 8080

  #Create a TARP server prototype
  server = tarp.server.makeServer()

  #Register the function with the server
  server.addRPCEndpoint('my_function', my_function)
  server.addRPCEndpoint('describe_host', describe_host)


  #Start the server
  tarp.server.runServer(server, port=port)

if __name__ == "__main__":

  server()


