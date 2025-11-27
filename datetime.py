import machine
import ntptime

rtc = machine.RTC()

def update():
    global time_string
    # grab the current time from the ntp server and update the Pico RTC
    try:
        ntptime.settime()
    except OSError:
        print("Unable to contact NTP server")

    current_t = rtc.datetime()

    print(current_t)