#!/usr/bin/python3

import io
import fcntl
import time
import string

# Global flag to control polling execution
stop_threads = False

class AtlasI2C:
    long_timeout = 1.5  # the timeout needed to query readings and calibrations
    short_timeout = 0.5  # timeout for regular commands
    default_bus = 1  # the default bus for I2C on the newer Raspberry Pis, certain older boards use bus 0
    default_address = 98  # the default address for the sensor
    current_addr = default_address

    def __init__(self, address=default_address, bus=default_bus):
        self.file_read = io.open(f"/dev/i2c-{str(bus)}", "rb", buffering=0)
        self.file_write = io.open(f"/dev/i2c-{str(bus)}", "wb", buffering=0)
        self.set_i2c_address(address)

    def set_i2c_address(self, addr):
        I2C_SLAVE = 0x703
        fcntl.ioctl(self.file_read, I2C_SLAVE, addr)
        fcntl.ioctl(self.file_write, I2C_SLAVE, addr)
        self.current_addr = addr

    def write(self, cmd):
        cmd += "\00"
        self.file_write.write(cmd.encode())

    def read(self, num_of_bytes=31):
        res = self.file_read.read(num_of_bytes)
        response = bytes([x for x in res if x != 0x00])
        if response and response[0] == 1:
            char_list = [chr(x & ~0x80) for x in response[1:]]
            return "Command succeeded " + ''.join(char_list)
        else:
            return "Error reading response"

    def query(self, string):
        self.write(string)
        if string.upper().startswith(("R", "CAL")):
            time.sleep(self.long_timeout)
        elif string.upper().startswith("SLEEP"):
            return "sleep mode"
        else:
            time.sleep(self.short_timeout)
        return self.read()

    def close(self):
        self.file_read.close()
        self.file_write.close()

    def list_i2c_devices(self):
        prev_addr = self.current_addr
        i2c_devices = []
        for i in range(128):
            try:
                self.set_i2c_address(i)
                self.read()
                i2c_devices.append(i)
            except IOError:
                pass
        self.set_i2c_address(prev_addr)
        return i2c_devices

def identify_sensor(device):
    try:
        response = device.query("I")
        if response.startswith("Command succeeded"):
            # Parse the response to extract sensor type
            sensor_info = response.split(",")[1] if ',' in response else "Unknown sensor"
            return sensor_info
        else:
            return "Unknown sensor"
    except IOError:
        return "Error in communication"

def poll_device(device, delaytime):
    global stop_threads
    stop_threads = False  # Reset flag before polling
    sensor_info = device.query("I")
    info = sensor_info.split(',')[1] if ',' in sensor_info else "Unknown sensor"
    print(f"Polling {info} every {delaytime:.2f} seconds, press Ctrl+C to stop polling.")
    
    try:
        while not stop_threads:
            response = device.query("R")
            print(f"Response: {response}")  # Debug print to see the actual response
            time.sleep(max(0, delaytime - AtlasI2C.long_timeout))
    except KeyboardInterrupt:
        print("Continuous polling stopped")
        stop_threads = True  # Ensure we set stop_threads to True here

def main():
    global stop_threads
    # List of I2C addresses for the new sensors
    device_addresses = [0x61, 0x62, 0x63, 0x65, 0x66]  # Updated device addresses
    devices = [AtlasI2C(address=addr) for addr in device_addresses]
    current_device = AtlasI2C()

    print(">> Atlas Scientific sample code")
    print(">> Available commands:")
    print(">>   LIST_ADDR - Lists the available I2C addresses.")
    print(">>   ADDRESS,xx - Change the I2C address to xx (in hexadecimal).")
    print(">>   POLL,xx.x - Poll the board every xx.x seconds.")
    print(">> Pressing Ctrl+C will stop the polling.")

    # Identify all connected devices
    sensor_names = {}
    for device in devices:
        sensor_type = identify_sensor(device)
        sensor_names[device.current_addr] = sensor_type
        print(f"Device at 0x{device.current_addr:02X}: {sensor_type}")


    while True:
        try:
            user_input = input("Enter command: ")
            if user_input.upper().startswith("LIST_ADDR"):
                available_devices = current_device.list_i2c_devices()
                for addr in available_devices:
                    print(f"Device found at address: 0x{addr:02X}")
            elif user_input.upper().startswith("ADDRESS"):
                try:
                    addr = int(user_input.split(',')[1], 16)  
                    if 0 <= addr <= 127:
                        current_device.close()  # Close current device communication
                        current_device = AtlasI2C(address=addr)  # Re-initialize with new address
                        print(f"I2C address set to 0x{addr:02X}")
                    else:
                        print("Address must be between 0x00 and 0x7F")
                except ValueError:
                    print("Invalid address format. Please use hexadecimal (e.g., ADDRESS,1A)")
            elif user_input.upper().startswith("POLL"):
                try:
                    delaytime = float(user_input.split(',')[1])
                    if delaytime < AtlasI2C.long_timeout:
                        print(f"Polling time is shorter than timeout, setting polling time to {AtlasI2C.long_timeout:.2f} seconds.")
                        delaytime = AtlasI2C.long_timeout

                    poll_device(current_device, delaytime)
                except ValueError:
                    print("Invalid poll time format. Please enter a valid number (e.g., POLL,2)")
            else:
                if not user_input:
                    print("Please input a valid command.")
                else:
                    try:
                        print(current_device.query(user_input))
                    except IOError:
                        print("Query failed - Address may be invalid, use LIST_ADDR command to see available addresses")
        except KeyboardInterrupt:
            print("Program stopped by keyboard interrupt.")
            break  # Exit the while loop to end the program

if __name__ == '__main__':
    main()
