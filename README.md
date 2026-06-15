# Entropy Zero

An AI-driven Multi-Robot Task Allocation and Scheduling System designed to optimize retail restocking operations through intelligent task prioritization, autonomous robot selection, and real-time visualization.

## Overview

Modern retail environments require efficient coordination among multiple autonomous robots for inventory management and restocking. Traditional task allocation methods often lead to inefficient routing, uneven workload distribution, and delayed responses to critical inventory needs.

**Entropy Zero** addresses these challenges by implementing an intelligent coordination agent that dynamically assigns tasks based on priority, robot proximity, workload, and availability.

---

## Objectives

- Intelligent task scheduling using priority-based allocation
- Reduced task completion time through optimal pathfinding
- Improved robot utilization and battery efficiency
- Balanced workload distribution across robots
- Explainable AI-powered decision making
- Real-time visualization and monitoring

---

## Problem Statement

Current retail automation systems face several challenges:

- Inefficient robot assignment using First-Come-First-Served approaches
- Lack of urgency awareness for critical tasks
- Uneven workload distribution among robots
- Limited transparency in automated decision-making

Entropy Zero solves these issues through AI-powered scheduling and intelligent robot coordination.

---

## System Architecture

### Event-Driven Workflow

```text
Restock Request (JSON)
          │
          ▼
      Watchdog
   (Event Detection)
          │
          ▼
   Task Coordinator
(Priority Scheduling)
          │
          ▼
   Robot Selection
(Distance + Workload)
          │
          ▼
    A* Pathfinding
          │
          ▼
   Task Assignment
          │
          ▼
Real-Time Visualization

---

## Technical Stack
Python
├── Pandas
├── Watchdog
├── Pygame
├── NiceGUI
├── Ollama
└── LLaMA 3

Algorithms
├── A* Pathfinding
├── Priority Scheduling
└── Heuristic Robot Selection

Architecture
├── Event-Driven System
├── Multi-Agent Coordination
└── Explainable AI
