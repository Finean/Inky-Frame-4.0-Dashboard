#import gc
from machine import Pin, SPI, reset
import time
import inky_frame
import helper as ih
import datetime
import sdcard
import os
import gc
import qrcode
import network
import urequests
import json
import pico_server as server
import uasyncio as asyncio

from picographics import PicoGraphics, DISPLAY_INKY_FRAME_4 as DISPLAY  # 4.0"
from breakout_bme69x import BreakoutBME69X, STATUS_HEATER_STABLE, FILTER_COEFF_3, STANDBY_TIME_1000_MS, OVERSAMPLING_16X, OVERSAMPLING_2X, OVERSAMPLING_1X

# A short delay to give USB chance to initialise
time.sleep(0.5)

def init(WIFI_PASSWORD, WIFI_SSID):
    inky_frame.led_busy.brightness(1.0)
    inky_frame.led_busy.on()
    ih.clear_button_leds()
    
    try:
        ih.network_connect(WIFI_SSID, WIFI_PASSWORD)
        print("Connected to {}".format(WIFI_SSID))
        wifi = True
    except ImportError:
        print("Create secrets.py with your WiFi credentials")
        wifi = False

    #Initialise BME690
    try:
        bme = BreakoutBME69X(machine.I2C(), 0x76)
        bme.configure(FILTER_COEFF_3, STANDBY_TIME_1000_MS, OVERSAMPLING_16X, OVERSAMPLING_2X, OVERSAMPLING_1X)
        sensor = True
    except:
        sensor = False
        print("No sensor detected")

    #Colours are BLACK, WHITE, GREEN, BLUE, RED, YELLOW, ORANGE, TAUPE
    graphics = PicoGraphics(DISPLAY)
    WIDTH, HEIGHT = graphics.get_bounds()
    graphics.set_pen(inky_frame.WHITE)
    graphics.clear()
    graphics.set_font("bitmap8")
    inky_frame.led_busy.off()

    #Initialise storage
    sd_spi = SPI(0, sck=Pin(18, Pin.OUT), mosi=Pin(19, Pin.OUT), miso=Pin(16, Pin.OUT))
    sd = sdcard.SDCard(sd_spi, Pin(22))
    
    #Initialise time
    if wifi:
        datetime.update()
        print("Time synced with NTP server")
    else:
        print("Unable to update machine RTC")
    
    gc.collect()
    return(graphics, sd, bme, wifi, sensor)


def textbox(gfx, text, x1, y1, w, text_colour, box_colour, text_size = 4, align = "left", offset = [5,5], font_size = 8, draw = True): #Multiline does not support alignments
    tex_len = gfx.measure_text(text, text_size)
    if (w - 2 * offset[0]) % tex_len == 0:
        lines = (tex_len // (w - 2 * offset[0]))
    else:
        lines = (tex_len // (w - 2 * offset[0])) + 1
    height = (lines * font_size * text_size) + (2 * offset[1]) + (lines - 1) * text_size
    
    #Do not draw into nav menu
    if y1 + height > 370:
        return(0)
    #Draw Box
    if draw:
        gfx.set_pen(box_colour)
        gfx.rectangle(x1, y1, w, height)
        gfx.set_pen(text_colour)
        if align == "center" and lines == 1:
            gfx.text(text, x1 + (w - tex_len)//2, y1 + offset[1], wordwrap = w - 2 * offset[0], scale = text_size)
        else:
            gfx.text(text, x1 + offset[0], y1 + offset[1], wordwrap = w - 2 * offset[0], scale = text_size)      
    return(height)


def nav_buttons(gfx, arr = [None, None, None, None, None], c_sec = None): #Array of length 5
    while len(arr) < 5:
        arr.append(None)
    # 64 + 128*n
    gfx.set_pen(inky_frame.BLACK)
    x_vals = [64, 192, 320, 448, 576]
    gfx.line(0,371, 640, 371, 2)
    for i in range(5):
        if arr[i] is None:
            continue
        else:
            text_len = gfx.measure_text(arr[i], 3)
            if c_sec == arr[i]:
                gfx.set_pen(inky_frame.BLACK)
                gfx.rectangle(x_vals[i] - 64, 370, 128, 30)
                gfx.set_pen(inky_frame.WHITE)
            else:
                gfx.set_pen(inky_frame.BLACK)
            gfx.text(arr[i], x_vals[i] - (text_len // 2), 378, wordwrap = text_len + 10, scale = 3)


def measure_qr_code(size, code):
    w, h = code.get_size()
    module_size = int(size / w)
    return module_size * w, module_size


def draw_qr_code(ox, oy, size, code):
    size, module_size = measure_qr_code(size, code)
    graphics.set_pen(1)
    graphics.rectangle(ox, oy, size, size)
    graphics.set_pen(0)
    for x in range(size):
        for y in range(size):
            if code.get_module(x, y):
                graphics.rectangle(ox + x * module_size, oy + y * module_size, module_size, module_size)


def dashboard():
    WIDTH = 640
    HEIGHT = 400
    global sensor
    
    year, month, day, dow, hour, minute, second, _ = machine.RTC().datetime()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    
    if minute < 10:
        minute = "0" + str(minute)
    else:
        minute = str(minute)
        
    graphics.set_pen(inky_frame.WHITE)
    graphics.clear()
    
    height = textbox(graphics, "{}:{}  {}, {} {}".format(hour, minute, days[dow], day, months[month-1]), 0, 0, WIDTH, inky_frame.BLACK, inky_frame.YELLOW) + 5
    
    #Read values from BME690
    if sensor:
        try:
            temp, press, humid, _, _, _, _ = bme.read()
            height_2 = textbox(graphics, "{} C".format(round(temp,1)), 0, height, WIDTH, inky_frame.WHITE, inky_frame.GREEN) + 5
            graphics.set_pen(inky_frame.WHITE)
            offset = graphics.measure_text("{} hPa".format(round(press / 100, 1)), 4) // 2
            graphics.text("{} hPa".format(round(press / 100, 1)), (WIDTH // 2) - offset , height + 5, WIDTH, scale = 4)
            offset = graphics.measure_text("{}%".format(round(humid, 1)), 4)
            graphics.text("{}%".format(round(humid, 1)), WIDTH - offset - 5 , height + 5, WIDTH, scale = 4)
            height += height_2
        except Exception as e:
            height += textbox(graphics, "Sensor Error", 0, height, WIDTH, inky_frame.WHITE, inky_frame.RED) + 5
            print("Error reading sensor data: ", e)          
            
    nav_buttons(graphics, ["Home", "WX: Now", "Hourly", "Daily", "Settings"], "Home")
    
    ih.pulse_network_led()
    try:
        url = "https://content.guardianapis.com/search?page-size=3&section=world|politics|business&api-key={}".format(ih.cfg["API_KEY"])
        response = urequests.get(url)
        news_data = response.json()
        response.close()
        news_size = news_data["response"]["pageSize"]
        for i in range(news_size):
            c_title = (
                news_data["response"]["results"][i]["webTitle"]
                    .replace("‘","\'")
                    .replace("’","\'")
                    .replace("–","-")
                    .replace("€", "EUR")
            )
            c_draw_size = textbox(graphics, "{}".format(c_title), 0, height, WIDTH, inky_frame.WHITE, inky_frame.BLUE, text_size = 3)
            if c_draw_size == 0:
                break
            else:
                height += c_draw_size + 5
    except Exception as e:
        textbox(graphics, "Error Loading News data", 0, height, WIDTH, inky_frame.WHITE, inky_frame.BLUE)
        print("Error Loading News information: ", e) 
        
    ih.stop_network_led()
    ih.network_led_pwm.duty_u16(30000)
    ih.clear_button_leds()
    ih.led_warn.on()
    graphics.update()
    gc.collect()
    ih.led_warn.off()
    
    
def home():
    
    last_update = None
    global update_interval

    while True:
        if last_update is None:
            _, _, _, dow, hour, minute, second, _ = machine.RTC().datetime()
            last_update = second + 60 * (minute + 60 * (hour + 24 * dow)) 
            dashboard()
            time.sleep(0.5)
        if ih.inky_frame.button_a.read():
            ih.inky_frame.button_a.led_on()
            ih.update_cfg("run", "Home")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_b.read():
            ih.inky_frame.button_b.led_on()
            ih.update_cfg("run", "wx_now")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_c.read():
            ih.inky_frame.button_c.led_on()
            ih.update_cfg("run", "wx_hourly")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_d.read():
            ih.inky_frame.button_d.len_on()
            ih.update_cfg("run", "wx_daily")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_e.read():
            ih.inky_frame.button_e.led_on()
            ih.update_cfg("run", "settings")
            time.sleep(0.5)
            reset()
            
        _, _, _, dow, hour, minute, second, _ = machine.RTC().datetime()
        cur_time = second + 60 * (minute + 60 * (hour + 24 * dow))
        if abs(cur_time - last_update) > update_interval:
            reset()
            
       
def weather(state = "now"):
    global wifi
    global location
    global location_name
    global update_interval
    WIDTH = 640
    HEIGHT = 400
    
    _, month, day, dow, hour, minute, second, _ = machine.RTC().datetime()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    last_update = second + 60 * (minute + 60 * (hour + 24 * dow)) 
    
    if minute < 10:
        minute = "0" + str(minute)
    else:
        minute = str(minute)
        
    graphics.set_pen(inky_frame.WHITE)
    graphics.clear()
    
    height = textbox(graphics, "{}:{}  {}, {} {}".format(hour, minute, days[dow], day, months[month-1]), 0, 0, WIDTH, inky_frame.BLACK, inky_frame.YELLOW) + 5
    
    if state == "now":
        c_sec = "WX: Now"
    elif state == "hourly":
        c_sec = "Hourly"
    elif state == "daily":
        c_sec = "Daily"
    else:
        c_sec = None
   
    nav_buttons(graphics, ["Home", "WX: Now", "Hourly", "Daily", "Settings"], c_sec)
    
    if location is None:
        height += textbox(graphics, "No Location", 0, height, WIDTH, inky_frame.WHITE, inky_frame.BLUE) + 5
    else:
        height += textbox(graphics, "{}".format(location_name), 0, height, WIDTH, inky_frame.WHITE, inky_frame.BLUE) + 5
        
    if not(wifi):
        height += textbox(graphics, "No network connection", 0, height, WIDTH, inky_frame.BLACK, inky_frame.WHITE) + 5
    else:
        height += 10
        if state == "now":
            try:
                ih.pulse_network_led()
                url = "https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current=temperature_2m,apparent_temperature,wind_direction_10m,wind_speed_10m,weather_code,is_day&timezone=auto".format(location[0], location[1])
                response = urequests.get(url)
                data = response.json()
                response.close()
                ih.stop_network_led()
                ih.network_led_pwm.duty_u16(30000)
        
                temperature = data["current"]["temperature_2m"]
                apparent = data["current"]["apparent_temperature"]
                
                tod = data["current"]["is_day"]
                code = data["current"]["weather_code"]
                
                wspeed = data["current"]["wind_speed_10m"]
                winddir = data["current"]["wind_direction_10m"]
                dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                ix = int((winddir + 11.25)/22.5)
                direction = dirs[ix % 16]
            
                height += textbox(graphics, "{} C".format(temperature), 10, height, WIDTH, inky_frame.BLACK, inky_frame.WHITE) + 5
                
                try:
                    w_data = json.loads(open("/weathercodes.json", "r").read())
                    if tod == 1:
                        description = w_data[str(code)]["day"]["description"]
                    else:
                        description = w_data[str(code)]["night"]["description"]
                    height += textbox(graphics, "{}".format(description), 10, height, WIDTH, inky_frame.BLACK, inky_frame.WHITE) + 5
                except Exception as e_2:
                    print("Error parsing weather code:", e_2)
                    
                height += textbox(graphics, "Feels like {} C".format(apparent), 10, height, WIDTH, inky_frame.BLACK, inky_frame.WHITE) + 5
                height += textbox(graphics, "{} km/h from {}".format(wspeed, direction), 10, height, WIDTH, inky_frame.BLACK, inky_frame.WHITE) + 5
            except Exception as e:
                textbox(graphics, "Error loading weather data, try restarting", 0, height, WIDTH, inky_frame.WHITE, inky_frame.RED, 4)
                print("Error fetching current weather: ", e)
                
                
        elif state == "hourly":
            try:
                ih.pulse_network_led()
                url = "https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&hourly=temperature_2m,precipitation_probability,wind_speed_10m,wind_direction_10m,weather_code&forecast_days=2&timezone=auto".format(location[0], location[1])
                response = urequests.get(url)
                data = response.json()
                response.close()
                ih.stop_network_led()
                ih.network_led_pwm.duty_u16(30000)
                
                temps = data["hourly"]["temperature_2m"]
                precip_prob = data["hourly"]["precipitation_probability"]
                wind_speeds = data["hourly"]["wind_speed_10m"]
                wind_dirs = data["hourly"]["wind_direction_10m"]
                dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                
                if int(minute) > 50:
                    hour += 1
                
                for i in range(5):
                    if i == 0:
                        disp_t = "Now"
                    else:
                        disp_t = "{}:00".format((hour + i) % 24)
                    ix = int((wind_dirs[hour + i] + 11.25)/22.5)
                    disp_dir = dirs[ix % 16]
                    
                    stackheight = height + textbox(graphics, "{}".format(disp_t), 128 * i, height, 128, inky_frame.BLACK, inky_frame.WHITE, 4, align = "center") + 10
                    stackheight += textbox(graphics, "{} C".format(temps[hour + i]), 128 * i, stackheight, 128, inky_frame.RED, inky_frame.WHITE, 3, align = "center") + 5
                    if precip_prob[hour + i] > 0:
                        r_col = inky_frame.BLUE
                    else:
                        r_col = inky_frame.BLACK
                    stackheight += textbox(graphics, "{}% Rain".format(precip_prob[hour + i]), 128 * i, stackheight, 128, r_col, inky_frame.WHITE, 3, align = "center") + 10
                    stackheight += textbox(graphics, "{}".format(wind_speeds[hour + i]), 128 * i, stackheight, 128, inky_frame.BLACK, inky_frame.WHITE, 3, align = "center") + 5
                    stackheight += textbox(graphics, "km/h", 128 * i, stackheight, 128, inky_frame.BLACK, inky_frame.WHITE, 3, align = "center") + 5
                    stackheight += textbox(graphics, "{}".format(disp_dir), 128 * i, stackheight, 128, inky_frame.BLACK, inky_frame.WHITE, 3, align = "center") + 5
                graphics.line(128 , height - 10, 128, 370, 2)
                graphics.line(256 , height - 10, 256, 370, 2)
                graphics.line(384 , height - 10, 384, 370, 2)
                graphics.line(512 , height - 10, 512, 370, 2)
                
            except Exception as e:
                textbox(graphics, "Error loading weather data, try restarting", 0, height, WIDTH, inky_frame.WHITE, inky_frame.RED, 4)
                print("Error fetching current weather: ", e)
    
    
        elif state == "daily":
            try:
                ih.pulse_network_led()
                url = "https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&daily=weather_code,temperature_2m_max,temperature_2m_min,rain_sum&timezone=auto".format(location[0], location[1])
                response = urequests.get(url)
                data = response.json()
                response.close()
                ih.stop_network_led()
                ih.network_led_pwm.duty_u16(30000)
                
                t_max = data["daily"]["temperature_2m_max"]
                t_min = data["daily"]["temperature_2m_min"]
                w_code = data["daily"]["weather_code"]
                rain_sum = data["daily"]["rain_sum"]
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                
                for i in range(5):
                    if i == 0:
                        disp_t = "Today"
                    else:
                        disp_t = "{}".format(days[(dow + i) % 7])
                    

                        
                    stackheight = height + textbox(graphics, "{}".format(disp_t), 128 * i, height, 128, inky_frame.BLACK, inky_frame.WHITE, 3, align = "center", offset = [2,5]) + 10
                    stackheight += textbox(graphics, "{} C".format(t_max[i]), 128 * i, stackheight, 128, inky_frame.GREEN, inky_frame.WHITE, 3, align = "center") + 5
                    stackheight += textbox(graphics, "{} C".format(t_min[i]), 128 * i, stackheight, 128, inky_frame.RED, inky_frame.WHITE, 3, align = "center") + 10
                    stackheight += textbox(graphics, "{}mm".format(rain_sum[i]), 128 * i, stackheight, 128, inky_frame.BLUE, inky_frame.WHITE, 3, align = "center") + 5
                    stackheight += textbox(graphics, "Rain", 128 * i, stackheight, 128, inky_frame.BLUE, inky_frame.WHITE, 3, align = "center") + 10
                    
                    code = w_code[i]
                    try:
                        w_data = json.loads(open("/weathercodes.json", "r").read())
                        description = w_data[str(code)]["day"]["description"]
                        textbox(graphics, "{}".format(description), 128 * i + 10, stackheight, 108, inky_frame.BLACK, inky_frame.WHITE, 2)
                    except Exception as e_2:
                        print("Error parsing weather code:", e_2)
                    
                graphics.line(128 , height - 10, 128, 370, 2)
                graphics.line(256 , height - 10, 256, 370, 2)
                graphics.line(384 , height - 10, 384, 370, 2)
                graphics.line(512 , height - 10, 512, 370, 2)
                
            except Exception as e:
                textbox(graphics, "Error loading weather data, try restarting", 0, height, WIDTH, inky_frame.WHITE, inky_frame.RED, 4)
                print("Error fetching current weather: ", e)
        else:
            textbox(graphics, "Error loading weather page, try restarting the device.", 0, height, WIDTH, inky_frame.WHITE, inky_frame.RED, 4)
                
    ih.stop_network_led()
    ih.network_led_pwm.duty_u16(30000)            
    ih.clear_button_leds()
    ih.led_warn.on()
    graphics.update()
    ih.led_warn.off()
    gc.collect()
    
    ih.load_cfg()
    while True:
        if ih.inky_frame.button_a.read():
            ih.inky_frame.button_a.led_on()
            ih.update_cfg("run", "Home")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_b.read():
            ih.inky_frame.button_b.led_on()
            ih.update_cfg("run", "wx_now")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_c.read():
            ih.inky_frame.button_c.led_on()
            ih.update_cfg("run", "wx_hourly")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_d.read():
            ih.inky_frame.button_d.led_on()
            ih.update_cfg("run", "wx_daily")
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_e.read():
            ih.inky_frame.button_e.led_on()
            ih.update_cfg("run", "settings")
            time.sleep(0.5)
            reset()
        
        _, _, _, dow, hour, minute, second, _ = machine.RTC().datetime()
        cur_time = second + 60 * (minute + 60 * (hour + 24 * dow))
        if abs(cur_time - last_update) > update_interval:
            reset()
         
         
async def settings():
    graphics.set_pen(inky_frame.WHITE)
    graphics.clear()
    nav_buttons(graphics, ["Home", "WX: Now", "Hourly", "Daily", "Refresh"], "Refresh")
    global wifi
    global sensor
    global location
    global update_interval
    
    pico_SSID = "PICO_W"
    pico_pass = "PICOWINKYFRAME4"
    pico_encryption = "WPA"
    
    
    asyncio.create_task(server.start_server(pico_SSID, pico_pass))
    
    while server.server_task is None:
        await asyncio.sleep(0.1)
        
    ip = server.ip
    print("Server started, drawing frame")
        
    graphics.set_pen(inky_frame.BLACK)
    
    if not(ip is None):
        wifi = f"WIFI:T:{pico_encryption};S:{pico_SSID};P:{pico_pass};;"
        code = qrcode.QRCode()
        code.set_text(wifi)
        draw_qr_code(430, 10, 200, code)
        code_2 = qrcode.QRCode()
        code_2.set_text(ip)
        draw_qr_code(430, 225, 120, code_2)
    else:
        graphics.line(430, 10, 630, 10, 2)
        graphics.line(430, 210, 630, 210, 2)
        graphics.line(430, 10, 430, 210, 2)
        graphics.line(630, 10, 630, 210, 2)
        graphics.text("Server Error", 437, 96, scale = 3)
        
    if wifi:
        graphics.text("Wifi: {}".format(ih.cfg["WIFI_SSID"]), 5, 5, scale = 3)
    else:
        graphics.text("Wifi: No Connection", 5, 5, scale = 3)
    if ih.cfg["API_KEY"] is None:
        graphics.text("API_Key: None", 5, 35, scale = 3)
    else:
        graphics.text("API_Key: True", 5, 35, scale = 3)
        
    if sensor:
        graphics.text("Sensor: Connected", 5, 65, scale = 3)
    else:
        graphics.text("Sensor: No Connection", 5, 65, scale = 3)
        
    if location == None:
        graphics.text("Location: None", 5, 95, scale = 3)
    else:
        graphics.text("Location: {}".format(location), 5, 95, scale = 3)
    if ih.cfg["LOCATION_NAME"] is None:
        graphics.text(ih.cfg["Unknown Location"], 5, 125, scale = 3)
    else:
        graphics.text(ih.cfg["LOCATION_NAME"], 5, 125, scale = 3)	
        
    graphics.text("Update Interval: {} mins".format(update_interval // 60), 5, 155, scale = 3)
    graphics.text("RAM: {}/{}KB".format(gc.mem_alloc()//1024, (gc.mem_alloc() + gc.mem_free())//1024), 5, 185, scale = 3)
    graphics.text("Scan the upper QR code to connect to pico, then scan the lower QR code to change settings. Or go to {}".format(ip), 5, 215, wordwrap = 400, scale = 3)
    
    
    
    ih.clear_button_leds()    
    ih.led_warn.on()
    graphics.update()       
    gc.collect()
    ih.led_warn.off()
    
    while True:
        if ih.inky_frame.button_a.read():
            ih.inky_frame.button_a.led_on()
            ih.update_cfg("run", "home")
            await server.stop_server()
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_b.read():
            ih.inky_frame.button_b.led_on()
            ih.update_cfg("run", "wx_now")
            await server.stop_server()
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_c.read():
            ih.inky_frame.button_c.led_on()
            ih.update_cfg("run", "wx_hourly")
            await server.stop_server()
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_d.read():
            ih.inky_frame.button_d.led_on()
            ih.update_cfg("run", "wx_daily")
            await server.stop_server()
            time.sleep(0.5)
            reset()
        if ih.inky_frame.button_e.read():
            ih.inky_frame.button_e.led_on()
            await server.stop_server()
            time.sleep(0.5)
            reset()

#Initialise
ih.led_warn.on()
ih.load_cfg()
location_name = ih.cfg["LOCATION_NAME"]
location = ih.cfg["LOCATION"]
update_interval = ih.cfg["UPDATE_INTERVAL"]
graphics, sd, bme, wifi, sensor = init(ih.cfg["WIFI_PASSWORD"], ih.cfg["WIFI_SSID"])

#Main Loop
while True:
    if ih.file_exists("config.json"):
        ih.load_cfg()
        if ih.cfg["run"] == "home" or ih.cfg["run"] is None:
            home()
        elif ih.cfg["run"] == "settings":
            asyncio.run(settings())
        elif ih.cfg["run"] == "wx_now":
            weather("now")
        elif ih.cfg["run"] == "wx_hourly":
            weather("hourly")
        elif ih.cfg["run"] == "wx_daily":
            weather("daily")
        else:
            ih.update_cfg("run", "home")
    else:
        ih.update_cfg("run", "home")
    gc.collect()