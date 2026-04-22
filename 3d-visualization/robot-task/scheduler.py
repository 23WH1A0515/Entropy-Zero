import math
import time

def a_star_cost(start, goal):
    return abs(start[0] - goal[0]) + abs(start[1] - goal[1])

def schedule_task(task, bots_dict):
    best_robot = None
    min_score = float('inf')

    for r_id, r_info in bots_dict.items():
        # Only select robots that are not currently on a mission
        if r_info.get('status') != 'FREE':
            continue

        travel_cost = a_star_cost(
            [r_info["x"], r_info["z"]],
            task["location"]
        )

        wait_time = 0  # simplified
        score = travel_cost + wait_time - (task["urgency"] * 2)

        if score < min_score:
            min_score = score
            best_robot = r_id

    return best_robot