import json
import math
import heapq
import time
import random
import asyncio
from nicegui import ui, app
from google import genai
from watchdog.observers import Observer

# ✅ IMPORTING YOUR BACKEND MODULES
from scheduler import schedule_task
from task_loader import load_tasks
from watchdog_handler import TaskHandler

# --- 1. CONFIGURATION & AI SETUP ---
try:
    with open('config.json', 'r') as f:
        data = json.load(f)
        config = data[0] if isinstance(data, list) else data
except Exception:
    config = {"api_key": "YOUR_KEY_HERE", "num_robots": 2}

client = genai.Client(api_key=config.get('api_key'))

robot_templates = {
    'R-100': {'home_x': -85, 'home_z': -25, 'color': '#facc15'},
    'R-200': {'home_x': -85, 'home_z': 25,  'color': '#ef4444'},
    'R-300': {'home_x': 85,  'home_z': -25, 'color': '#3b82f6'},
    'R-400': {'home_x': 85,  'home_z': 25,  'color': '#10b981'},
}

active_bots = {}
targets = []
sc = None
observer = None # Prevents double-starting on Mac

# --- 2. 3D MODELS ---
def draw_robot(scene, accent_color, name):
    with scene.group() as robot:
        scene.box(4, 1.2, 5).material('#1e293b')
        for dx, dz in [(-1.5, -2), (1.5, -2), (-1.5, 2), (1.5, 2)]:
            scene.cylinder(0.6, 0.6, 0.8).material('#0f172a').move(x=dx, z=dz).rotate(math.pi/2, 0, 0)
        scene.box(3, 3.5, 3.5).material(accent_color).move(y=2)
        scene.cylinder(0.8, 0.8, 0.4).material('#000000').move(y=4)
        slot = scene.group().move(y=1.5, z=2.5)
        scene.text(name).move(y=6.5).scale(2.5)
    return robot, slot

def draw_warehouse(scene):
    scene.box(230, 0.1, 140).material('#edc9af') # Light Teak Floor
    scene.box(30, 20, 70).material('#1e293b', opacity=0.9).move(x=-100, y=10)
    scene.box(30, 20, 70).material('#1e293b', opacity=0.9).move(x=100, y=10)

    for col_x in [-45, -15, 15, 45]:
        for row_z in [-25, 0, 25]:
            with scene.group().move(x=col_x, z=row_z):
                scene.box(0.6, 22, 6).material('#475569').move(x=-3.5, y=11)
                scene.box(0.6, 22, 6).material('#475569').move(x=3.5, y=11)
                for ly in [2, 8, 14]:
                    scene.box(7, 0.4, 6).material('#fbbf24').move(y=ly)

# --- 3. CORE LOGIC ---
def add_log(msg, color='text-slate-400', ai=False):
    prefix = "🤖 AI:" if ai else "»"
    with log_container:
        ui.label(f"{prefix} {msg}").classes(f'font-mono text-[10px] {color} {"italic text-yellow-500" if ai else ""}')

async def move_robot_3d(bot_key, tx, ty, tz):
    b = active_bots[bot_key]
    sx, sz = b['x'], b['z']
    steps = 55
    for i in range(steps + 1):
        t = i / steps
        ease = t*t*(3-2*t)
        b['x'], b['z'] = sx + (tx - sx) * ease, sz + (tz - sz) * ease
        b['model'].move(x=b['x'], z=b['z'])
        b['slot'].move(y=1.5 + (ty * t))
        await asyncio.sleep(0.01)

# ✅ THE EXECUTOR: This connects your Watchdog to your existing run_mission logic
async def execute_task_flow(task):
    # Use your scheduler.py logic
    bot_id = schedule_task(task, active_bots)
    
    if not bot_id:
        add_log("No available robots for incoming task.", "text-red-400")
        return

    # Find matching shelf slot from your targets list
    target = next((t for t in targets if t['x'] == task['location'][0] and t['z'] == task['location'][1] and t['status'] == 'EMPTY'), None)
    
    if target:
        add_log(f"Dispatching {bot_id} to {task['item_id']}", "text-cyan-400")
        asyncio.create_task(run_mission(bot_id, target, task['urgency']))
    else:
        add_log(f"Target at {task['location']} is full or invalid.", "text-orange-400")

async def run_mission(bot_key, target, urgency):
    b = active_bots[bot_key]; b['status'] = 'BUSY'
    try:
        resp = client.models.generate_content(model="gemini-1.5-flash", contents=f"Why {bot_key} for {target['id']}?")
        add_log(resp.text.strip(), ai=True)
    except:
        add_log(f"Mission: {bot_key} fetching unit for {target['id']}.", ai=True)

    with b['slot']: cargo = sc.box(3.5, 3, 3.5).material('#a16207')
    await move_robot_3d(bot_key, target['x'], target['y'], target['z'] - 7)
    
    cargo.delete()
    with sc: 
        target['box_obj'] = sc.box(3.5, 3, 3.5).material('#a16207').move(x=target['x'], y=target['y']+1.7, z=target['z'])
    
    target['status'] = 'FILLED'
    add_log(f"{bot_key}: RESTOCK SUCCESS", 'text-green-400')
    
    await asyncio.sleep(0.5)
    await move_robot_3d(bot_key, b['home_x'], 0, b['home_z'])
    b['status'] = 'FREE'

# --- 4. PAGE DEFINITION ---
@ui.page('/')
def main_page():
    global log_container, sc, bot_select, targets, active_bots
    targets, active_bots = [], {}

    # Initializing 36 unique shelf slots
    for col_x in [-45, -15, 15, 45]:
        for row_z in [-25, 0, 25]:
            for level_y in [2, 8, 14]:
                targets.append({
                    'id': f'Slot_{col_x}_{row_z}_L{level_y}',
                    'x': col_x, 'y': level_y, 'z': row_z,
                    'status': 'EMPTY' # Start empty so tasks can fill them
                })

    with ui.column().classes('w-full h-screen no-wrap bg-slate-950'):
        with ui.row().classes('w-full p-4 bg-slate-900 border-b-2 border-yellow-500 justify-between items-center'):
            ui.label('ARCHIVE CORE').classes('text-2xl font-black text-slate-100 italic')
            with ui.row().classes('gap-4 items-center'):
                ui.label('NUMBER OF ROBOTS:').classes('text-white text-xs font-bold')
                bot_select = ui.select([1, 2, 3, 4], value=2).classes('w-24 bg-slate-800 rounded text-cyan-400 font-bold border border-cyan-500/30')
                ui.button('TOP VIEW', on_click=lambda: sc.move_camera(y=145, z=0, duration=1)).props('color=green text-white')
                ui.button('ISO VIEW', on_click=lambda: sc.move_camera(x=85, y=55, z=-85, duration=1)).props('color=green text-white')
                ui.button('INITIATE', on_click=start_simulation).props('color=yellow text-black font-bold px-8')
                ui.button('RESET', on_click=lambda: ui.run_javascript('window.location.reload()')).props('flat color=red')

        with ui.row().classes('w-full grow no-wrap'):
            with ui.column().classes('p-6 w-80 bg-slate-900/50 backdrop-blur'):
                ui.label('TELEMETRY LOG').classes('text-[10px] font-bold text-yellow-500 mb-4 tracking-widest')
                log_container = ui.column().classes('gap-1 w-full')
            with ui.scene(width=1300, height=850, grid=False).classes('grow bg-black') as scene_ref:
                global sc
                sc = scene_ref
                sc.move_camera(x=0, y=35, z=-125, look_at_x=0, look_at_y=5, look_at_z=0)
                draw_warehouse(sc)

def start_simulation():
    global observer
    if active_bots: return # Safety check
    
    count = int(bot_select.value)
    add_log(f"SYSTEM: ENGAGING {count} UNITS", 'text-yellow-400')
    for i in range(count):
        name = f'R-{i+1}'
        template = list(robot_templates.values())[i]
        model, slot = draw_robot(sc, template['color'], name)
        active_bots[name] = {
            'x': template['home_x'], 'z': template['home_z'],
            'home_x': template['home_x'], 'home_z': template['home_z'],
            'status': 'FREE', 'model': model, 'slot': slot
        }
        model.move(x=template['home_x'], z=template['home_z'])

    # ✅ INITIALIZE WATCHDOG
    if observer is None:
        observer = Observer()
        # Pass the executor function and the current event loop
        handler = TaskHandler(execute_task_flow, asyncio.get_event_loop())
        observer.schedule(handler, path=".", recursive=False)
        observer.start()
        add_log("WATCHDOG ACTIVE: Listening for incoming_tasks.json", "text-cyan-400")

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Archive Core 5.5", dark=True, reload=False)