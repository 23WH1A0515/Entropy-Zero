import json
import time

def load_tasks():
    try:
        # Give the OS a millisecond to finish writing the file
        time.sleep(0.1) 
        with open("incoming_tasks.json", "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"Error loading tasks: {e}")
        return []