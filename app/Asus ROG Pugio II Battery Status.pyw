import hid
import time
import threading
from PIL import Image, ImageDraw, ImageTk
import pystray
import tkinter as tk
from tkinter import ttk
import sys
import winreg
import os
import subprocess
import msvcrt


VENDOR_ID = 0x0B05
PRODUCT_IDS_WITH_BATTERY = [0x1908, 0x1906]
REPORT_ID = 0x00
BATTERY_REPORT_PACKET = bytes([REPORT_ID, 0x12, 0x07])
USB_PACKET_SIZE = 65
UPDATE_INTERVAL = 5

status_window = None
root = None
icon = None

LOCK_FILE = os.path.join(os.getenv('TEMP'), 'rog_mouse_battery.lock')
lock_fp = None

def enforce_single_instance():
    global lock_fp
    try:
        lock_fp = open(LOCK_FILE, 'w')
        msvcrt.locking(lock_fp.fileno(), msvcrt.LK_NBLCK, 1)
    except IOError:
        print("Aplikácia už beží. Ukončujem...")
        sys.exit(0)

def release_lock():
    global lock_fp
    if lock_fp:
        try:
            msvcrt.locking(lock_fp.fileno(), msvcrt.LK_UNLCK, 1)
            lock_fp.close()
            os.remove(LOCK_FILE)
        except Exception:
            pass

def is_windows_light_theme():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        winreg.CloseKey(key)
        return value == 1
    except Exception:
        return True

def get_battery_info():
    dev = None
    try:
        for pid in PRODUCT_IDS_WITH_BATTERY:
            devices = hid.enumerate(VENDOR_ID, pid)
            if not devices:
                continue

            device_info = next((d for d in devices if b'MI_00' in d['path']), devices[0])
            dev = hid.device()
            dev.open_path(device_info['path'])

            full_packet = BATTERY_REPORT_PACKET + bytes([0x00] * (USB_PACKET_SIZE - len(BATTERY_REPORT_PACKET)))
            dev.write(full_packet)
            time.sleep(0.05)
            response = dev.read(USB_PACKET_SIZE)
            if response and len(response) >= 5 and response[0] == 0x12 and response[1] == 0x07:
                battery_value_raw = response[4]
                battery_percentage = battery_value_raw * 25
                is_charging = (pid == 0x1906)
                return battery_percentage, is_charging

        return None, False

    except Exception:
        return None, False

    finally:
        if dev:
            try:
                dev.close()
            except:
                pass

def create_image(color):
    image = Image.new('RGB', (64, 64), color='white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return image

def update_icon(icon):
    battery, charging = get_battery_info()
    
    if battery is None:
        icon.title = "Nepripojené"
        try:
            icon.icon = Image.open("assets/images/not_connected.png")
        except Exception as e:
            print("Chyba pri načítaní obrázku not_connected.png:", e)
        return

    title = f"Batéria: {battery}%"
    
    if charging:
        title += " (nabíja sa)"
        try:
            icon.icon = Image.open("assets/images/charging.png")
        except Exception as e:
            print("Chyba pri načítaní obrázku charging.png:", e)
    else:
        if battery >= 75:
            icon_path = "assets/images/green.png"
        elif battery >= 50:
            icon_path = "assets/images/orange.png"
        elif battery >= 25:
            icon_path = "assets/images/orange.png"
        else:
            icon_path = "assets/images/red.png"

        try:
            icon.icon = Image.open(icon_path)
        except Exception as e:
            print(f"Chyba pri načítaní obrázku {icon_path}:", e)

    icon.title = title


def auto_update(icon):
    while True:
        update_icon(icon)
        time.sleep(UPDATE_INTERVAL)

def close_status_window():
    global status_window
    if status_window is not None:
        status_window.destroy()
        status_window = None

def show_status_window(battery, charging):
    global status_window, root
    if status_window is not None:
        status_window.lift()
        return

    light_theme = is_windows_light_theme()
    bg_color = "SystemButtonFace" if light_theme else "#2D2D30"
    fg_color = "black" if light_theme else "white"

    status_window = tk.Toplevel(root)
    status_window.title("Stav batérie")
    status_window.geometry("320x120")
    status_window.resizable(False, False)
    status_window.attributes("-topmost", True)
    status_window.overrideredirect(True)
    status_window.configure(bg=bg_color)


    status_window.update_idletasks()
    screen_width = status_window.winfo_screenwidth()
    screen_height = status_window.winfo_screenheight()
    win_width = 320
    win_height = 120
    x = screen_width - win_width - 10
    y = screen_height - win_height - 60
    status_window.geometry(f"{win_width}x{win_height}+{x}+{y}")

    frame = tk.Frame(status_window, bg=bg_color, padx=10, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    label = tk.Label(
        frame,
        text="Asus ROG Pugio II",
        font=("Segoe UI", 12, "bold"),
        anchor="center",
        background=bg_color,
        fg=fg_color,
        justify="center"
    )
    label.pack(fill=tk.X, pady=(0, 5))

    canvas = tk.Canvas(frame, width=300, height=60, bg=bg_color, highlightthickness=0)
    canvas.pack()

    try:
        mouse_img_pil = Image.open("assets/images/mouse.png").resize((70, 70), Image.Resampling.LANCZOS)
        mouse_img_tk = ImageTk.PhotoImage(mouse_img_pil)
        status_window.mouse_img_tk = mouse_img_tk
        canvas.create_image(35, 30, image=mouse_img_tk)
    except Exception as e:
        print("Chyba pri načítaní mouse.png:", e)

    if battery is None:
        canvas.create_text(120, 30, text="Nepripojené", font=("Segoe UI", 16), fill="red" if light_theme else "orange", anchor="w")
    else:
        bat_x = 85
        bat_y1 = 20
        bat_y2 = 50
        outline_color = "black" if light_theme else "white"
        fill_color = "green" if battery >= 50 else "orange" if battery >= 20 else "red"
        canvas.create_rectangle(bat_x, bat_y1, bat_x + 120, bat_y2, outline=outline_color, width=2)
        canvas.create_rectangle(bat_x + 120, 27, bat_x + 125, 43, outline=outline_color, fill=outline_color)

        fill_width = int((battery / 100) * 118)
        canvas.create_rectangle(bat_x + 2, bat_y1 + 2, bat_x + 2 + fill_width, bat_y2 - 2, fill=fill_color, width=0)

        margin_right = 30
        text_x = 300 - margin_right
        canvas.create_text(text_x, 35, text=f"{battery}%", font=("Segoe UI", 12), anchor="e", fill=fg_color)

        if charging:
            canvas.create_text(bat_x + 60, 33, text="⚡", font=("Segoe UI Emoji", 16), fill="#ffbf00")

    def close_after_delay():
        time.sleep(2.5)
        try:
            root.after(0, close_status_window)
        except:
            pass

    threading.Thread(target=close_after_delay, daemon=True).start()


def on_show_status(icon, item):
    battery, charging = get_battery_info()
    root.after(0, show_status_window, battery, charging)

def quit_app(icon, item):
    global root
    def stop_all():
        icon.stop()
        release_lock()
        if root:
            root.quit()
            root.destroy()
        sys.exit(0)

    if root:
        root.after(0, stop_all)

def run_icon_thread():
    global icon
    icon.run()

def on_armoury_create(icon, item):
    try:
        ps_command = (
            'Start-Process shell:$("AppsFolder\\" + '
            '(Get-AppxPackage | Where-Object {$_.PackageFamilyName -like \'*ArmouryCrate*\'}).PackageFamilyName + "!App")'
        )

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        subprocess.run(
            ["powershell", "-Command", ps_command],
            check=True,
            startupinfo=startupinfo
        )
        print("Armoury Crate spustený cez PowerShell dynamicky.")
    except Exception as e:
        print("Chyba pri spustení Armoury Crate cez PowerShell:", e)

def main():
    global root, icon
    root = tk.Tk()
    root.withdraw()

    icon = pystray.Icon("ROG Strix Impact II")
    icon.icon = create_image("gray")
    icon.title = "Inicializácia..."

    icon.menu = pystray.Menu(
        pystray.MenuItem('Zobraziť stav batérie', on_show_status, default=True),
        pystray.MenuItem('Armoury Crate', on_armoury_create),
        pystray.MenuItem('Ukončiť', quit_app)
    )

    update_icon(icon)

    threading.Thread(target=auto_update, args=(icon,), daemon=True).start()
    threading.Thread(target=run_icon_thread, daemon=True).start()

    root.mainloop()

if __name__ == "__main__":
    enforce_single_instance()
    main()


