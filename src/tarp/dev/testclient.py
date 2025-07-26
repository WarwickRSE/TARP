from sys import argv
import re

import tarp.client

def validate_ip(ip_str):

  if ip_str == 'localhost':
    return

  #Ip matching regex from “Regular Expressions Cookbook by Jan Goyvaerts and Steven Levithan. Copyright 2009 Jan Goyvaerts and Steven Levithan, 978-0-596-2068-7.”

  regex = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
  regex = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
  reg_c = re.compile(regex)

  if(re.match(reg_c, ip_str)) is None:
    print("Warning: you have not chosen 'localhost' nor a valid IP address\n Assuming a hostname, continuing")


def client():

  if(len(argv) > 1):
    ip_str = argv[1]
    validate_ip(ip_str)
  else:
    ip_str = 'localhost'

  print("Connecting to "+ip_str)

  if(len(argv) > 2):
    #Assuming port
    try:
      port = int(argv[2])
    except:
      print("Invalid port specified: " + argv[2]+"\n Falling back to 8080")
      port = 8080
  else:
    port = 8080

  try:
    client = tarp.client.client('http://{}:{}'.format(ip_str,port))
  except Exception as e:
    print("Connection failed with error: ")
    print(e)
    exit()


  server_info = client.describe_host()

  print("Connected to host:")
  print(server_info)



  result = client.my_function(1, 2)
  print("Function returned: {} (expected {})".format(result, 3))  # Output: 3

if __name__ == "__main__":

  client()

