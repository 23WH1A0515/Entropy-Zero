from watchdog.events import FileSystemEventHandler
import asyncio
from task_loader import load_tasks

class TaskHandler(FileSystemEventHandler):
    def __init__(self, executor, loop):
        self.executor = executor
        self.loop = loop

    def on_modified(self, event):
        # Only trigger for our specific JSON file
        if event.src_path.endswith("incoming_tasks.json"):
            tasks = load_tasks()
            for task in tasks:
                # Thread-safe call back to the main NiceGUI loop
                self.loop.call_soon_threadsafe(
                    lambda t=task: asyncio.create_task(self.executor(t))
                )