import network
import time
import socket
import helper as ih
import machine
import ure
import json
import uasyncio as asyncio

server_task = None
ip = None
s = None

def urldecode(s):
    return s.replace("%20", " ").replace("%2C", ",")


def urlspace(s):
    return s.replace("+", " ")


def web_page():
    ih.load_cfg()
    net_ssid = ih.cfg["WIFI_SSID"]
    net_pass = ih.cfg["WIFI_PASSWORD"]
    api_key = ih.cfg["API_KEY"]
    loc_name = ih.cfg["LOCATION_NAME"]
    lat = ih.cfg["LOCATION"][0]
    long = ih.cfg["LOCATION"][1]
    interval = str(ih.cfg["UPDATE_INTERVAL"])
    html = """
    <html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Settings Form</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 40px;
      background-color: #f9f9f9;
    }
    h1 {
      color: #333;
    }
    form {
      max-width: 400px;
      padding: 20px;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 8px;
    }
    label {
      display: block;
      margin-top: 15px;
      font-weight: bold;
    }
    input[type="text"] {
      width: 100%;
      padding: 8px;
      margin-top: 5px;
      border: 1px solid #ccc;
      border-radius: 4px;
    }
    button {
      margin-top: 20px;
      padding: 10px 15px;
      background: #0078d7;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }
    button:hover {
      background: #005a9e;
    }
  </style>
</head>
""" + """
<body>
  <h1>Device Settings</h1>
  <form method="GET" action="/">
  <label>Wifi SSID:</label>
  <input type="text" name="wifi_ssid" value="{net_ssid}">

  <label>Wifi Password:</label>
  <input type="text" name="wifi_password" value = "{net_pass}">

  <label>API Key:</label>
  <input type="text" name="api_key" value = "{api_key}">

  <label>Latitude:</label>
  <input type="text" name="loc_lat" value="{lat}">

  <label>Longitude:</label>
  <input type="text" name="loc_lon" value="{long}">

  <label>Location Name:</label>
  <input type="text" name="loc_name" value="{loc_name}">

  <label>Update Interval (Seconds):</label>
  <input type="text" name="upd_int" value="{interval}">

  <button type="submit">Submit</button>
</form>
<form method="GET" action="/reset">
  <button type="submit">Restart Device</button>
</form>
</body>
</html>
""".format(net_ssid = net_ssid, lat = lat, long = long, loc_name = loc_name, interval = interval, net_pass = net_pass, api_key = api_key)
    return html


async def handle_client(conn):
    request = conn.recv(1024)
    request_str = request.decode()
    print("Request: ", request_str)
    
    if "GET /reset" in request_str:
        await conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
        await conn.send("<html><body><h1>Resetting...</h1></body></html>")
        await conn.close()
        machine.reset()  # <-- triggers Pico reset
    elif "GET /?" in request_str:
        query_part = request_str.split("GET /?")[1]
        query_string = query_part.split(" ")[0]
            
        params = query_string.split("&")
             
        settings = {}
        for p in params:
            if "=" in p:
                key, value = p.split("=", 1)
                settings[key] = urldecode(value)
                    
        settings["loc_name"] = urlspace(settings["loc_name"])
        print("Parsed settings:", settings)
            
        if not(settings["loc_lon"] is None) and not(settings["loc_lat"] is None):
            try:
                temp = [float(settings["loc_lat"]), float(settings["loc_lon"])]
                ih.update_cfg("LOCATION", temp)
            except:
                print("Error parsing Location Data")
        if settings["loc_name"] != "":
            ih.update_cfg("LOCATION_NAME", settings["loc_name"])
        if settings["wifi_ssid"] != "":
            ih.update_cfg("WIFI_SSID", settings["wifi_ssid"])
            ih.update_cfg("WIFI_PASSWORD", settings["wifi_password"])
        if settings["api_key"] != "":
            ih.update_cfg("API_KEY", settings["api_key"])
        if settings["upd_int"] != "":
            try:
                ih.update_cfg("UPDATE_INTERVAL", int(settings["upd_int"]))
            except:
                print("Error parsing update interval")
                    
        print(ih.cfg)
    else:
        response = web_page()
        conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
        conn.send(response)
        conn.close()


async def start_server(ssid, password):
    global server_task, ip
    ih.load_cfg()
    # Just making our internet connection
    ap = network.WLAN(network.AP_IF)
    ap.config(essid = ssid, password = password.encode())
    ap.active(True)
    
    while ap.active() == False:
        await asyncio.sleep(0.1)
    print('Server Running...')
    print('IP Address To Connect to:: ' + ap.ifconfig()[0])
    ip = ap.ifconfig()[0]
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   #creating socket object
    s.bind(('', 80))
    s.listen(5)
    s.settimeout(0.5)
    
    server_task = True
    while server_task:
        print("Awaiting connection...")
        try:
            conn, addr = s.accept()
            print("Connected to:", addr)
            await handle_client(conn)
        except:
            pass
        await asyncio.sleep(0)

   
async def stop_server():
    global server_task
    server_task = False
    ap = network.WLAN(network.AP_IF)
    await asyncio.sleep(1.0)
    ap.active(False)
    print("Server Stopped")
    
   
async def test():
    asyncio.create_task(start_server("PICO_W", "PICOWINKYFRAME4"))
    await asyncio.sleep(30)
    await stop_server()
    print("Program Complete")
    
#asyncio.run(test())
