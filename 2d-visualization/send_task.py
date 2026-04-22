import json
import os
import shutil

# 1. Folders
TARGET_DIR = "./input_requests"
SOURCE_FILE = "scalable_orders.json"  # The file I converted for you

def send_bulk_orders():
    # Ensure the target directory exists
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

    # Check if our scalability file exists
    if os.path.exists(SOURCE_FILE):
        # We copy the file into the watched folder with a new name
        destination = os.path.join(TARGET_DIR, "bulk_scalability_test.json")
        shutil.copy(SOURCE_FILE, destination)
        
        # Let's count how many items we just sent
        with open(SOURCE_FILE, 'r') as f:
            data = json.load(f)
            count = len(data)
            
        print(f"🚀 SUCCESS: Sent {count} urgent tasks to the fleet!")
        print(f"📂 File moved to: {destination}")
    else:
        print(f"❌ ERROR: {SOURCE_FILE} not found. Make sure it's in the same folder!")

if __name__ == "__main__":
    send_bulk_orders()