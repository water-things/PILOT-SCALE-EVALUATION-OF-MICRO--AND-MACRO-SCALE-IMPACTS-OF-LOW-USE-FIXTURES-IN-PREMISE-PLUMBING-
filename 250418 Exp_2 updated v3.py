#!/usr/bin/env python3# -*- coding: utf-8 -*-'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''\|                                                                                || This code was developed to facilitate automated control of a solenoid valve    || and collection of sensor data for experimental analysis of water quality       || changes within a pilot scale premise plumbing pipe rig system. The system      || utilizes a Raspberry Pi 3 Model B to facilitate these goals. The code was      || developed in part for work funded by the NSF Award #2027444: Proactive Water   | | Quality Management of Water Networks in Buildings. See citation below for full | | publication. Code written by ASU PhD student D. Hogue in 2024. Contact D. Hogue|| (dahogue@asu.edu) or T.H. Boyer (thboyer@su.edu) for more information.         ||                                                                                ||                                                                                ||                         !!! IMPORTANT !!!                                      || csv_file_path and schedule_df need to be updated by user for proper execution  || ^ line 179        ^ line 186                                                   ||                                                                                |'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''import RPi.GPIO as GPIOimport timeimport datetimeimport pandas as pdfrom smbus2 import SMBusimport osimport threadingimport sys# Global flags to control thread executionstop_threads = Falseshutdown_initiated = False  # Global variables for the threadsvalve_thread = Nonedata_thread = Noneclass AtlasI2C:    def __init__(self, address, bus):        self.address = address        self.bus = bus    def query(self, command):        try:            self.bus.write_byte(self.address, ord(command))            time.sleep(1)            response = self.bus.read_i2c_block_data(self.address, 0, 10)            response_string = ''.join(chr(x) for x in response if 32 <= x < 127)            return response_string        except IOError as e:            print(f"Sensor read error at address {self.address}: {e}")            return Nonedef setup_gpio():    GPIO.setmode(GPIO.BCM)    GPIO.setup(23, GPIO.OUT)    GPIO.output(23, GPIO.LOW)  # Initialize valve to closed positiondef valve_control(schedule_df):    global stop_threads    global valve_position    last_event_index = -1      while not stop_threads:        try:            current_time = datetime.datetime.now().replace(second=0, microsecond=0)            hour = current_time.hour            minute = current_time.minute            # Reset event index at 20:00 for multi-day execution            if hour == 20 and last_event_index != -1:                last_event_index = -1                print("Event index reset for the next day.")                continue              # Filter the events scheduled for the current hour and minute            events = schedule_df[(schedule_df['Hour'] == hour) & (schedule_df['Minute'] == minute)]            # Iterate over all events scheduled for the current time            for _, event in events.iterrows():                event_index = event['Event_Index']                # Skip the event if it has already been processed                if event_index <= last_event_index:                    continue                event_type = event['Type']                event_duration = 10 if event_type == 'Use' else 400  # Event duration in s                GPIO.output(23, GPIO.HIGH)                  time.sleep(0.1)                  valve_position = 'Open'                print(f"\nValve opened for {event_duration} seconds due to {event_type} event, Event Index: {event_index}\n")                time.sleep(event_duration)                if stop_threads:                    break                GPIO.output(23, GPIO.LOW)  # Close the valve                time.sleep(0.1)                  valve_position = 'Closed'                print("\n------Valve closed------\n")                last_event_index = event_index  # Update the last processed event index            # Adjust sleep time to dynamically align with the start of the next second            time_to_next_second = 1.0 - (datetime.datetime.now().microsecond / 1000000.0)            time.sleep(time_to_next_second)        except Exception as e:            print(f"Error in valve_control: {e}")def data_collection(sensor_devices, file_path):    global stop_threads    global valve_position    current_time = datetime.datetime.now()    initial_delay = 10 - (current_time.second % 10) - (current_time.microsecond / 1000000.0)    if initial_delay > 5:        initial_delay -= 5    else:        initial_delay += 5    print(f"Initial time: {current_time}\n")    print(f"Initial delay: {initial_delay}s\n")    time.sleep(initial_delay)  # Wait until the next 10-second interval    next_time = time.time()    while not stop_threads:        try:            sensor_data = {label: sensor.query('R') for label, sensor in sensor_devices.items()}            current_time = datetime.datetime.now()            formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S') + f".{current_time.microsecond // 10000:02d}"            with open(file_path, 'a') as file:                data_line = f"{formatted_time},{','.join(sensor_data.values())},{valve_position}\n"                file.write(data_line)            print(f"Data logged at {formatted_time}")            if stop_threads:                break            next_time += 10  # Schedule next log for 10 seconds later            time.sleep(max(next_time - time.time(), 0))  # Sleep until the next scheduled time        except Exception as e:            print(f"Error in data_collection: {e}")def read_schedule(file_path):    df = pd.read_csv(file_path)    df['Hour'] = pd.to_datetime(df['Time_HMS'], format='%H:%M:%S').dt.hour    df['Minute'] = pd.to_datetime(df['Time_HMS'], format='%H:%M:%S').dt.minute    df['Type'] = df['Type'].astype(str)  # Ensure the "Type" column is read as a string    return dfdef safe_shutdown():    global shutdown_initiated    if shutdown_initiated:        return  # Prevent multiple executions of safe_shutdown    shutdown_initiated = True    print("Shutting down safely...")    # Signal the threads to stop    global stop_threads    stop_threads = True    # Ensure the valve is closed    try:        GPIO.output(23, GPIO.LOW)  # Ensure the valve is closed        print("Valve closed during shutdown.")    except Exception as e:        print(f"Error during GPIO shutdown: {e}")        # Clean up GPIO    GPIO.cleanup()    print("Resources have been cleaned up.")        sys.exit(0)# Initialize everythingsetup_gpio()bus = SMBus(1)sensor_addresses = {'DO': 0x61, 'ORP': 0x62, 'pH': 0x63, 'EC': 0x65, 'Temp': 0x66}sensor_devices = {label: AtlasI2C(address, bus) for label, address in sensor_addresses.items()}# csv_file_path = '/home/~' # UPDATE FOR USE os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)valve_position = 'Closed'  # Update valve positionwith open(csv_file_path, 'a') as file:    file.write("Timestamp,DO,ORP,pH,EC,Temp,Valve_Position\n")# schedule_df = read_schedule('/home/~') # UPDATE FOR USE# Start threadsvalve_thread = threading.Thread(target=valve_control, args=(schedule_df,))valve_thread.daemon = True  data_thread = threading.Thread(target=data_collection, args=(sensor_devices, csv_file_path))data_thread.daemon = True  valve_thread.start()data_thread.start()# Keep the main program running until an interrupt is receivedtry:    while not stop_threads:        time.sleep(0.1)except KeyboardInterrupt:    safe_shutdown()finally:    if not shutdown_initiated:        safe_shutdown()  # Ensure cleanup is done even if an error occurs