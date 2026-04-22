import pygame
import os
import json
import math
import ollama
import heapq
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Thread

# --- CONFIG & THEME ---
WIDTH, HEIGHT = 1100, 750
GRID_AREA = 750
GRID_SIZE = 15
CELL_SIZE = GRID_AREA // GRID_SIZE
WATCH_DIR = "./input_requests"

# Cyberpunk Palette
BG_DARK = (10, 12, 18)
PANEL_COLOR = (18, 20, 28)
ACCENT_CYAN = (0, 255, 240)
ACCENT_MAGENTA = (255, 0, 150)
ROBOT_1_COLOR = (255, 60, 120)
ROBOT_2_COLOR = (0, 180, 255)
SHELF_COLOR = (45, 50, 70)
SHELF_TOP = (70, 80, 110)

# --- DATA ---
SHELVES = [(3, i) for i in range(2, 13)] + [(8, i) for i in range(2, 13)] + [(12, i) for i in range(2, 13)]
robots = {
    "R1": {"pos": [0, 0], "path": [], "color": ROBOT_1_COLOR, "target": None, "busy": False, "pulse": 0},
    "R2": {"pos": [14, 14], "path": [], "color": ROBOT_2_COLOR, "target": None, "busy": False, "pulse": 0}
}
task_queue = []
ai_logs = ["SYSTEM READY", "ENCRYPTION ACTIVE..."]

# --- PATHFINDING ---
def a_star(start, goal):
    start, goal = tuple(start), tuple(goal)
    frontier = [(0, start)]
    came_from, cost_so_far = {start: None}, {start: 0}
    while frontier:
        curr = heapq.heappop(frontier)[1]
        if curr == goal: break
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            nxt = (curr[0]+dx, curr[1]+dy)
            if 0 <= nxt[0] < GRID_SIZE and 0 <= nxt[1] < GRID_SIZE and nxt not in SHELVES:
                new_cost = cost_so_far[curr] + 1
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + math.dist(nxt, goal)
                    heapq.heappush(frontier, (priority, nxt))
                    came_from[nxt] = curr
    path = []
    while goal in came_from:
        path.append(goal); goal = came_from[goal]
    return path[::-1]

# --- UI DRAWING HELPERS ---
def draw_3d_shelf(screen, x, y, is_target=False):
    px, py = x * CELL_SIZE, y * CELL_SIZE
    base_col = ACCENT_CYAN if is_target else SHELF_COLOR
    # Shadow/Side
    pygame.draw.rect(screen, (20, 25, 35), (px + 5, py + 5, CELL_SIZE - 4, CELL_SIZE - 4), border_radius=4)
    # Main Body
    pygame.draw.rect(screen, base_col, (px + 2, py + 2, CELL_SIZE - 6, CELL_SIZE - 10), border_radius=4)
    # Top Highlight
    pygame.draw.rect(screen, SHELF_TOP, (px + 4, py + 4, CELL_SIZE - 10, 5), border_radius=2)

def draw_robot(screen, info, font):
    rx, ry = int(info["pos"][0]*CELL_SIZE + CELL_SIZE//2), int(info["pos"][1]*CELL_SIZE + CELL_SIZE//2)
    color = info["color"]
    
    # Pulsing Aura
    info["pulse"] = (info["pulse"] + 0.1) % 6.28
    glow_size = 15 + math.sin(info["pulse"]) * 5
    
    s = pygame.Surface((60, 60), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, 60), (30, 30), glow_size)
    screen.blit(s, (rx - 30, ry - 30))
    
    pygame.draw.circle(screen, (30, 30, 30), (rx, ry), 12)
    pygame.draw.circle(screen, color, (rx, ry), 10, 2)
    pygame.draw.circle(screen, (255, 255, 255), (rx, ry), 4) # Eye
    
    if info["target"]:
        lbl = font.render(str(info["target"]), True, (255, 255, 255))
        screen.blit(lbl, (rx - lbl.get_width()//2, ry - 35))

# --- MAIN LOOP ---
class TaskHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith(".json"):
            import time; time.sleep(0.1)
            try:
                with open(event.src_path, 'r') as f:
                    data = json.load(f)
                items = data if isinstance(data, list) else [data]
                for i in items:
                    if i.get("final_restock_decision", True): 
                        task_queue.append(i)
                        ai_logs.append(f"QUEUED: {i['item_id']}")
            except: pass

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("ULTIMATE FLEET COMMAND")
    clock = pygame.time.Clock()
    
    f_main = pygame.font.SysFont("Agency FB", 32, bold=True)
    f_side = pygame.font.SysFont("Consolas", 14)

    os.makedirs(WATCH_DIR, exist_ok=True)
    obs = Observer(); obs.schedule(TaskHandler(), WATCH_DIR); obs.start()

    running = True
    while running:
        screen.fill(BG_DARK)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False

        # 1. DRAW GRID FLOOR
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                pygame.draw.rect(screen, (15, 18, 25), (x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE), 1)

        # 2. DRAW 3D SHELVES (Fixed for interaction)
        for sx, sy in SHELVES:
            # Check if any robot is targeting this specific spot
            is_targeted = any(r["target_loc"] == (sx, sy) for r in robots.values() if r["busy"])
            draw_3d_shelf(screen, sx, sy, is_targeted)

        # 3. TASK ASSIGNMENT
        for r_id, info in robots.items():
            if not info["busy"] and task_queue:
                task = task_queue.pop(0)
                target = tuple(task["location"])
                info["target_loc"] = target # Store raw target for shelf highlight
                
                # Logic to stop NEXT to shelf, not on it
                if target in SHELVES:
                    # Move to the tile to the left of the shelf
                    target = (target[0]-1, target[1])
                
                path = a_star((int(round(info["pos"][0])), int(round(info["pos"][1]))), target)
                if path:
                    info.update({"path": path, "target": task["item_id"], "busy": True})
                    # AI Thread call
                    msg = f"Robot {r_id} is fetching {task['item_id']}. Give a 1-sentence professional log update."
                    Thread(target=lambda: ai_logs.append(f"AI: {ollama.chat(model='llama3', messages=[{'role': 'user', 'content': msg}])['message']['content']}")).start()

        # 4. UPDATE & DRAW ROBOTS
        for r_id, info in robots.items():
            if info["path"]:
                pts = [(p[0]*CELL_SIZE+CELL_SIZE//2, p[1]*CELL_SIZE+CELL_SIZE//2) for p in info["path"]]
                if len(pts) > 1: pygame.draw.lines(screen, (*info["color"], 80), False, pts, 2)
                
                nxt = info["path"][0]
                for i in range(2):
                    if info["pos"][i] < nxt[i]: info["pos"][i] += 0.08
                    elif info["pos"][i] > nxt[i]: info["pos"][i] -= 0.08
                
                if math.dist(info["pos"], nxt) < 0.1:
                    info["pos"] = list(nxt); info["path"].pop(0)
                    if not info["path"]: 
                        ai_logs.append(f"SUCCESS: {r_id} completed task.")
                        info["busy"] = False; info["target"] = None; info["target_loc"] = None

            draw_robot(screen, info, f_side)

        # 5. DRAW DASHBOARD
        pygame.draw.rect(screen, PANEL_COLOR, (GRID_AREA, 0, 350, HEIGHT))
        pygame.draw.line(screen, ACCENT_CYAN, (GRID_AREA, 0), (GRID_AREA, HEIGHT), 2)
        screen.blit(f_main.render("FLEET TELEMETRY", True, ACCENT_CYAN), (GRID_AREA + 20, 20))
        
        # Queue Count
        pygame.draw.rect(screen, (30, 35, 50), (GRID_AREA+20, 70, 310, 40), border_radius=5)
        screen.blit(f_side.render(f"PENDING TASKS: {len(task_queue)}", True, (255, 255, 0)), (GRID_AREA+40, 82))

        # Logs
        for i, log in enumerate(ai_logs[-15:]):
            txt = f_side.render(f"> {log[:40]}", True, (100, 110, 130))
            screen.blit(txt, (GRID_AREA+20, 400 + (i*20)))

        pygame.display.flip()
        clock.tick(60)

    obs.stop(); pygame.quit()

if __name__ == "__main__": main()