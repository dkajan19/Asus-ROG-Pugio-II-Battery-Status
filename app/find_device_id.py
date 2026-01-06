import hid
import time
import re

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"

VENDOR_ID = 0x0B05
REPORT_ID = 0x00
BATTERY_REPORT_PACKET = bytes([REPORT_ID, 0x12, 0x07])
USB_PACKET_SIZE = 65
READ_TIMEOUT_MS = 1000

def get_battery_info():
    dev = None
    try:
        devices = hid.enumerate(VENDOR_ID, 0)
        if not devices:
            print(f"{CYAN}[INFO]{RESET} No devices found with Vendor ID {hex(VENDOR_ID)}")
            return None, False, None, None

        print(f"{CYAN}[INFO]{RESET} Found {len(devices)} device(s) with Vendor ID {hex(VENDOR_ID)}")
        print("============================================================")

        for index, device_info in enumerate(devices, start=1):
            path = device_info['path']
            pid = device_info['product_id']
            product = device_info.get('product_string', 'Unknown')
            manufacturer = device_info.get('manufacturer_string', 'Unknown')
            mi_match = re.search(r'MI_\d{2}', path.decode() if isinstance(path, bytes) else path)
            mi = mi_match.group(0) if mi_match else 'Unknown'

            print(f"\n{BOLD}{MAGENTA}Device #{index}{RESET}")
            print("------------------------------------------------------------")
            print(f"{CYAN}Product:{RESET}      {product}")
            print(f"{CYAN}Manufacturer:{RESET} {manufacturer}")
            print(f"{CYAN}PID:{RESET}          {hex(pid)}")
            print(f"{CYAN}Path:{RESET}         {path}")
            print(f"{CYAN}MI:{RESET}           {mi}")
            print("------------------------------------------------------------")

            try:
                dev = hid.device()
                dev.open_path(path)

                full_packet = BATTERY_REPORT_PACKET + bytes([0x00] * (USB_PACKET_SIZE - len(BATTERY_REPORT_PACKET)))
                dev.write(full_packet)
                time.sleep(0.05)
                response = dev.read(USB_PACKET_SIZE, timeout_ms=READ_TIMEOUT_MS)
                print(f"{MAGENTA}[DEBUG]{RESET} HID response: {response}")

                if response and len(response) >= 5 and response[0] == 0x12 and response[1] == 0x07:
                    battery_value_raw = response[4]
                    battery_percentage = battery_value_raw * 25
                    is_charging = (pid == 0x1906)
                    print(f"{GREEN}[SUCCESS]{RESET} Battery level: {battery_percentage}%")
                    print(f"{GREEN}[SUCCESS]{RESET} Charging: {'Yes' if is_charging else 'No'}")
                    return battery_percentage, is_charging, pid, mi
                else:
                    print(f"{YELLOW}[WARNING]{RESET} No valid battery data in response.")
            except Exception as e:
                print(f"{RED}[ERROR]{RESET} Exception for device path {path}: {e}")
            finally:
                if dev:
                    dev.close()
                    dev = None

        print(f"\n{RED}[ERROR]{RESET} No suitable HID device responded with battery info.")
        return None, False, None, None

    except Exception as outer_e:
        print(f"{RED}[FATAL]{RESET} Exception during device scan: {outer_e}")
        return None, False, None, None

# --------------------------
# Run for testing
# --------------------------

if __name__ == "__main__":
    battery, charging, pid, mi = get_battery_info()
    print(f"\n{BOLD}{GREEN}================ Final Result ================\n{RESET}")
    if battery is not None:
        status = f"{GREEN}Charging{RESET}" if charging else f"{YELLOW}Not Charging{RESET}"
        print(f"{CYAN}Battery:{RESET}    {battery}%")
        print(f"{CYAN}Status:{RESET}     {status}")
        print(f"{CYAN}Vendor ID:{RESET}  {hex(VENDOR_ID)}")
        print(f"{CYAN}Product ID:{RESET} {hex(pid)}")
        print(f"{CYAN}MI:{RESET}         {mi}")
    else:
        print(f"{RED}Battery information could not be retrieved.{RESET}")
