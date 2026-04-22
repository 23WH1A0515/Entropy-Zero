import json
import math
import heapq
import time
import random
import asyncio
from nicegui import ui, app
from google import genai

# --- 1. CONFIGURATION & AI SETUP ---
try:
    with open('config.json', 'r') as f:
        data = json.load(f)
        config = data[0] if isinstance(data, list) else data
except Exception:
    # Fallback if config.json is missing or corrupted
    config = {"api_key": "AIzaSyBl6eOMiFCUJmzjOo0tYADlq22ONBaDoJQ", "num_robots": 2}

# Modern GenAI client initialization
client = genai.Client(api_key=config.get('api_key'))

robot_templates = {
    'R-100': {'home_x': -85, 'home_z': -25, 'color': '#facc15'},
    'R-200': {'home_x': -85, 'home_z': 25,  'color': '#ef4444'},
    'R-300': {'home_x': 85,  'home_z': -25, 'color': '#3b82f6'},
    'R-400': {'home_x': 85,  'home_z': 25,  'color': '#10b981'},
}

# Global state holders (Reset on every page load)
active_bots = {}
task_queue = []
targets = []

# --- 2. 3D MODELS (FORKLIFTS & WAREHOUSE) ---
def draw_robot(scene, accent_color, name):
    with scene.group() as robot:
        scene.box(4, 1.2, 5).material('#1e293b') # Heavy Base
        for dx, dz in [(-1.5, -2), (1.5, -2), (-1.5, 2), (1.5, 2)]:
            scene.cylinder(0.6, 0.6, 0.8).material('#0f172a').move(x=dx, z=dz).rotate(math.pi/2, 0, 0)
        scene.box(3, 3.5, 3.5).material(accent_color).move(y=2) # Main Chassis
        scene.cylinder(0.8, 0.8, 0.4).material('#000000').move(y=4) # Lidar Sensor
        slot = scene.group().move(y=1.5, z=2.5) # Forklift Mast
        scene.text(name).move(y=6.5).scale(2.5)
    return robot, slot

def draw_warehouse(scene):
    # Polished Light Teak Floor
    scene.box(230, 0.1, 140).material('#edc9af') 
    
    # Hub Alpha and Hub Beta (Pickup points)
    scene.box(30, 20, 70).material('#1e293b', opacity=0.9).move(x=-100, y=10)
    scene.box(30, 20, 70).material('#1e293b', opacity=0.9).move(x=100, y=10)

    # 3-Level Rack Construction
    for col_x in [-45, -15, 15, 45]:
        for row_z in [-25, 0, 25]:
            with scene.group().move(x=col_x, z=row_z):
                scene.box(0.6, 22, 6).material('#475569').move(x=-3.5, y=11)
                scene.box(0.6, 22, 6).material('#475569').move(x=3.5, y=11)
                # 3 vertical levels per column
                for ly in [2, 8, 14]:
                    scene.box(7, 0.4, 6).material('#fbbf24').move(y=ly)

    # Render randomized inventory based on page-load state
    for t in targets:
        with scene.group().move(x=t['x'], y=t['y'], z=t['z']):
            glow_color = '#22c55e' if t['status'] == 'FILLED' else '#ef4444'
            t['glow'] = scene.box(6.8, 0.1, 5.8).material(glow_color, opacity=0.2).move(y=0.1)
            if t['status'] == 'FILLED':
                t['box_obj'] = scene.box(3.5, 3, 3.5).material('#a16207').move(y=1.7)

# --- 3. CORE LOGIC & AI ---
def add_log(msg, color='text-slate-400', ai=False):
    prefix = "🤖 AI:" if ai else "»"
    with log_container:
        ui.label(f"{prefix} {msg}").classes(f'font-mono text-[10px] {color} {"italic text-yellow-500" if ai else ""}')

async def move_robot_3d(bot_key, tx, ty, tz):
    b = active_bots[bot_key]
    sx, sz = b['x'], b['z']
    steps = 55
    for i in range(steps + 1):
        # Collision Avoidance (Multi-robot safety)
        for ok, ob in active_bots.items():
            if ok != bot_key:
                if math.dist([b['x'], b['z']], [ob['x'], ob['z']]) < 15:
                    await asyncio.sleep(0.06)
        
        t = i / steps
        ease = t*t*(3-2*t)
        b['x'], b['z'] = sx + (tx - sx) * ease, sz + (tz - sz) * ease
        b['model'].move(x=b['x'], z=b['z'])
        # Smooth Fork Lifting to reach the target level
        b['slot'].move(y=1.5 + (ty * (i/steps))) 
        await asyncio.sleep(0.01)

async def run_mission(bot_key, target, urgency):
    b = active_bots[bot_key]; b['status'] = 'BUSY'
    try:
        # AI reasoning for path optimization
        prompt = f"Explain why {bot_key} was the best choice for {target['id']} at level {target['y']}."
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        add_log(response.text.strip(), ai=True)
    except Exception:
        add_log(f"Optimal path found: {bot_key} moving to Level {target['y']}.", ai=True)

    with b['slot']: cargo = sc.box(3.5, 3, 3.5).material('#a16207') # Pick up crate
    await move_robot_3d(bot_key, target['x'], target['y'], target['z'] - 7)
    
    cargo.delete() # Handover
    with sc: target['box_obj'] = sc.box(3.5, 3, 3.5).material('#a16207').move(x=target['x'], y=target['y']+1.7, z=target['z'])
    target['glow'].material('#22c55e', opacity=0.4); target['status'] = 'FILLED'
    add_log(f"{bot_key}: LEVEL {target['y']} RESTOCKED", 'text-green-400')
    
    await asyncio.sleep(0.5); await move_robot_3d(bot_key, b['home_x'], 0, b['home_z'])
    b['status'] = 'FREE'

async def dispatch_system():
    # Priority Queue Management
    for t in targets:
        if t['status'] == 'EMPTY':
            heapq.heappush(task_queue, (-random.randint(1,10), time.time(), t))
    
    while task_queue:
        free_ones = [k for k, v in active_bots.items() if v['status'] == 'FREE']
        if not free_ones: await asyncio.sleep(1); continue
        
        urg, _, target = heapq.heappop(task_queue)
        # Choosing the closest available unit
        best_bot = min(free_ones, key=lambda k: math.dist([active_bots[k]['x'], active_bots[k]['z']], [target['x'], target['z']]))
        asyncio.create_task(run_mission(best_bot, target, -urg))
        await asyncio.sleep(0.5)

# --- 4. PAGE DEFINITION ---
@ui.page('/')
def main_page():
    global log_container, sc, bot_select, targets, active_bots, task_queue
    
    # Resetting internal states on page load/reset
    targets = []
    active_bots = {}
    task_queue = []
    
    # Generate 3-level density shelves randomly
    for col_x in [-45, -15, 15, 45]:
        for row_z in [-25, 0, 25]:
            for level_y in [2, 8, 14]:
                is_filled = random.choice([True, False])
                targets.append({
                    'id': f'Slot_{col_x}_{row_z}_L{level_y}',
                    'x': col_x, 'y': level_y, 'z': row_z,
                    'glow': None, 'box_obj': None, 
                    'status': 'FILLED' if is_filled else 'EMPTY'
                })

    with ui.column().classes('w-full h-screen no-wrap bg-slate-950'):
        # Header Controls
        with ui.row().classes('w-full p-4 bg-slate-900 border-b-2 border-yellow-500 justify-between items-center'):
            ui.label('ENTROPY ZERO').classes('text-2xl font-black text-slate-100 italic')
            with ui.row().classes('gap-4 items-center'):
                ui.label('NUMBER OF ROBOTS:').classes('text-white text-xs font-bold')
                
                # UPDATED: Cyan bold text inside a dark slate box for high visibility
                bot_select = ui.select([1, 2, 3, 4], value=2).classes('w-24 bg-slate-800 rounded text-cyan-400 font-bold border border-cyan-500/30')
                
                ui.button('TOP VIEW', on_click=lambda: sc.move_camera(y=145, z=0, duration=1)).props('color=green text-white')
                ui.button('ISO VIEW', on_click=lambda: sc.move_camera(x=85, y=55, z=-85, duration=1)).props('color=green text-white')
                ui.button('INITIATE', on_click=start_simulation).props('color=yellow text-black font-bold px-8')
                ui.button('RESET', on_click=lambda: ui.run_javascript('window.location.reload()')).props('flat color=red')

        with ui.row().classes('w-full grow no-wrap'):
            # Sidebar Telemetry
            with ui.column().classes('p-6 w-80 bg-slate-900/50 backdrop-blur'):
                ui.label('TELEMETRY LOG').classes('text-[10px] font-bold text-yellow-500 mb-4 tracking-widest')
                log_container = ui.column().classes('gap-1 w-full')
            
            # 3D Scene
            with ui.scene(width=1300, height=850, grid=False).classes('grow bg-black') as sc:
                sc.move_camera(x=0, y=35, z=-125, look_at_x=0, look_at_y=5, look_at_z=0)
                draw_warehouse(sc)

def start_simulation():
    count = int(bot_select.value)
    add_log(f"SYSTEM: ENGAGING {count} UNITS", 'text-yellow-400')
    # Spawning selected robot fleet
    for i, (name, data) in enumerate(list(robot_templates.items())[:count]):
        model, slot = draw_robot(sc, data['color'], name)
        active_bots[name] = {
            'x': data['home_x'], 'z': data['home_z'],
            'home_x': data['home_x'], 'home_z': data['home_z'],
            'color': data['color'], 'status': 'FREE',
            'model': model, 'slot': slot
        }
        active_bots[name]['model'].move(x=data['home_x'], z=data['home_z'])
    
    asyncio.create_task(dispatch_system())

ui.run(title="Archive Core 5.2", dark=True)