import sys, time
from pywinauto import Application, Desktop, timings
import time, pyautogui
from pyscreeze import ImageNotFoundException

def findbuttonandclick(icon_path):
    save_btn = None
    # A) Fuzzy search (requires opencv-python)
    try:
        save_btn = pyautogui.locateOnScreen(
            icon_path,
            confidence=0.9
        )
    except (TypeError, ImageNotFoundException):
        # B) Exact match (pure Pillow)
        save_btn = pyautogui.locateOnScreen(
            icon_path,
            grayscale=True
        )
    pyautogui.click(pyautogui.center(save_btn))
        
# 1. Build cmd exactly as before
pythonw = sys.executable.replace("python.exe", "pythonw.exe")
script = r"D:\SynologyDrive\rpg\Python\GMCampaignDesigner2\main_window.py"
cmd = f'"{pythonw}" "{script}"'

# 2. Start the app (UIA backend)


# 1. Start your app without waiting for idle
app = Application(backend="uia").start(cmd, wait_for_idle=False)
time.sleep(1)  # give it a sec to pop up

# 2. Attach by title across _all_ windows
dlg = Desktop(backend="uia").window(title="MainWindowView")

# 3. Wait only for exists/visible/enabled
dlg.wait("exists visible enabled", timeout=10)

# 4. Now you can dump controls
dlg.print_control_identifiers()

# 5) Try a fuzzy match first, fallback to exact/grayscale
creature_path = r"auto-tests\images\creature_button.png"
pc_path = r"auto-tests\images\pc_button.png"

findbuttonandclick(creature_path)
wait = 5
time.sleep(wait)
findbuttonandclick(pc_path)

