import sys
import math
import base64
import re
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QTextEdit, QPushButton, QLabel
from PySide6.QtCore import QTimer, Qt, QThread, Signal, QBuffer, QIODevice, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from openai import OpenAI

# --- API WORKER ---
class ChatWorker(QThread):
    response_received = Signal(str)

    def __init__(self, api_key, history, image_base64=None):
        super().__init__()
        self.client = OpenAI(api_key=api_key)
        self.history = history
        self.image_base64 = image_base64

    def run(self):
        try:
            messages = [msg for msg in self.history]
            if self.image_base64 and messages[-1]["role"] == "user":
                text_content = messages[-1]["content"]
                messages[-1]["content"] = [
                    {"type": "text", "text": text_content},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{self.image_base64}", "detail": "high"}
                    }
                ]

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=600,
                temperature=0
            )
            self.response_received.emit(response.choices[0].message.content)
        except Exception as e:
            self.response_received.emit(f"OpenAI Error: {str(e)}")

# --- ROBOT SIMULATION ---
class RobotSim(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumWidth(800)
        self.setMouseTracking(True)
        self.CELL_SIZE = 80
        self.MARGIN_X, self.MARGIN_Y = 100, 150 
        self.COL_LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        self.ROW_LABELS = ['1', '2', '3', '4', '5']
        
        self.arm_visible = True
        self.bot_pos = [self.MARGIN_X + 40, self.MARGIN_Y + 40]
        self.bot_target = list(self.bot_pos)
        self.brick_pos = [self.MARGIN_X + 120, self.MARGIN_Y + 40]
        
        # Added Big Plate (Diameter = 160px = 2 boxes)
        self.extra_objects = [
            {"name": "Grey Box", "pos": [self.MARGIN_X + 120, self.MARGIN_Y - 80], "color": QColor(100, 100, 100), "type": "rect", "w": 40, "h": 40},
            {"name": "Water Bottle", "pos": [self.MARGIN_X + 220, self.MARGIN_Y - 80], "color": QColor(100, 150, 255), "type": "bottle", "w": 30, "h": 50},
            {"name": "Big Plate", "pos": [self.MARGIN_X + 400, self.MARGIN_Y - 80], "color": QColor(150, 75, 0), "type": "circle", "w": 160, "h": 160}
        ]
        
        self.holding = False
        self.held_extra = None
        self.speed = 15 
        self.dragging_obj = None
        self.drag_offset = QPoint(0, 0)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(16)

    def get_coords(self, col, row):
        try:
            c_idx = self.COL_LABELS.index(col.strip().upper())
            r_idx = 5 - int(row.strip())
            return (self.MARGIN_X + c_idx * self.CELL_SIZE + 40,
                    self.MARGIN_Y + r_idx * self.CELL_SIZE + 40)
        except: return None

    def update_physics(self):
        if self.dragging_obj: return
        dx, dy = self.bot_target[0] - self.bot_pos[0], self.bot_target[1] - self.bot_pos[1]
        dist = math.hypot(dx, dy)
        if dist > self.speed:
            self.bot_pos[0] += (dx / dist) * self.speed
            self.bot_pos[1] += (dy / dist) * self.speed
        else: self.bot_pos = list(self.bot_target)
            
        if self.holding:
            if self.held_extra == "brick": self.brick_pos = list(self.bot_pos)
            elif self.held_extra: self.held_extra["pos"] = list(self.bot_pos)
        self.update()

    def is_at_target(self):
        return math.hypot(self.bot_target[0] - self.bot_pos[0], self.bot_target[1] - self.bot_pos[1]) < 2

    def mousePressEvent(self, event):
        p = event.position().toPoint()
        if math.hypot(p.x() - self.bot_pos[0], p.y() - self.bot_pos[1]) < 40:
            self.dragging_obj, self.drag_offset = "bot", QPoint(p.x() - self.bot_pos[0], p.y() - self.bot_pos[1])
            return
        if abs(p.x() - self.brick_pos[0]) < 25 and abs(p.y() - self.brick_pos[1]) < 25:
            self.dragging_obj, self.drag_offset = "brick", QPoint(p.x() - self.brick_pos[0], p.y() - self.brick_pos[1])
            return
        for obj in self.extra_objects:
            if abs(p.x() - obj["pos"][0]) < obj["w"]/2 + 10 and abs(p.y() - obj["pos"][1]) < obj["h"]/2 + 10:
                self.dragging_obj, self.drag_offset = obj, QPoint(p.x() - obj["pos"][0], p.y() - obj["pos"][1])
                return

    def mouseMoveEvent(self, event):
        if self.dragging_obj:
            p = event.position().toPoint()
            new_x, new_y = p.x() - self.drag_offset.x(), p.y() - self.drag_offset.y()
            if self.dragging_obj == "bot": self.bot_pos = self.bot_target = [new_x, new_y]
            elif self.dragging_obj == "brick": self.brick_pos = [new_x, new_y]
            else: self.dragging_obj["pos"] = [new_x, new_y]
            self.update()

    def mouseReleaseEvent(self, event): self.dragging_obj = None

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.fillRect(self.rect(), QColor(10, 10, 20))
        
        # Shelf
        qp.setPen(QColor(60, 60, 80))
        qp.drawRect(self.MARGIN_X, self.MARGIN_Y - 170, 600, 150)
        qp.setPen(QColor(150, 150, 150))
        qp.drawText(self.MARGIN_X + 10, self.MARGIN_Y - 150, "STAGING AREA / SHELF")

        # Grid + AI Watermarks
        for c in range(8):
            for r in range(5):
                x, y = self.MARGIN_X + c * self.CELL_SIZE, self.MARGIN_Y + r * self.CELL_SIZE
                qp.setPen(QColor(40, 45, 60))
                qp.drawRect(x, y, self.CELL_SIZE, self.CELL_SIZE)
                qp.setPen(QColor(50, 50, 70))
                qp.drawText(x + 5, y + 20, f"{self.COL_LABELS[c]}{self.ROW_LABELS[4-r]}")

        # Drawing Objects
        def draw_obj(obj_type, x, y, w, h, color):
            qp.setBrush(color)
            qp.setPen(Qt.NoPen)
            if obj_type == "rect": qp.drawRect(int(x - w/2), int(y - h/2), w, h)
            elif obj_type == "circle": qp.drawEllipse(int(x - w/2), int(y - h/2), w, h)
            elif obj_type == "bottle":
                qp.drawRoundedRect(int(x - w/2), int(y - h/2), w, h, 5, 5)
                qp.drawRect(int(x - w/4), int(y - h/2 - 5), int(w/2), 5)

        for obj in self.extra_objects:
            draw_obj(obj["type"], obj["pos"][0], obj["pos"][1], obj["w"], obj["h"], obj["color"])
        draw_obj("rect", self.brick_pos[0], self.brick_pos[1], 40, 40, QColor(240, 240, 240))

        if self.arm_visible:
            # Gantry
            grid_top, grid_bottom = self.MARGIN_Y, self.MARGIN_Y + (5 * self.CELL_SIZE)
            grid_left, grid_right = self.MARGIN_X, self.MARGIN_X + (8 * self.CELL_SIZE)
            qp.setPen(QPen(QColor(50, 50, 60), 10))
            qp.drawLine(grid_left - 20, grid_top - 10, grid_right + 20, grid_top - 10)
            qp.drawLine(grid_left - 20, grid_bottom + 10, grid_right + 20, grid_bottom + 10)
            rail_x, head_y = self.bot_pos[0], self.bot_pos[1]
            qp.setPen(QPen(QColor(40, 100, 140), 14))
            qp.drawLine(int(rail_x), int(grid_top - 10), int(rail_x), int(grid_bottom + 10))
            qp.setBrush(QColor(30, 30, 30))
            qp.setPen(QPen(QColor(255, 140, 0), 2))
            qp.drawRect(int(rail_x - 25), int(head_y - 25), 50, 50)
            qp.setPen(QPen(QColor(200, 200, 200), 4))
            claw = 10 if self.holding else 25
            qp.drawLine(int(rail_x - 15), int(head_y + 25), int(rail_x - 15), int(head_y + 40))
            qp.drawLine(int(rail_x - 15), int(head_y + 40), int(rail_x - claw), int(head_y + 50))
            qp.drawLine(int(rail_x + 15), int(head_y + 25), int(rail_x + 15), int(head_y + 40))
            qp.drawLine(int(rail_x + 15), int(head_y + 40), int(rail_x + claw), int(head_y + 50))
        qp.end()

# --- MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prolabs V12.2 - Precision Cartesian Gantry")
        self.showMaximized()
        self.api_key = "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"
        
        system_prompt = """You are a Coordinate locator & planner for a Cartesian Gantry Robot.
1. Identify grid (A-H columns, 1-5 rows). 
2. Objects: 'White Brick' (Square), 'Grey Box' (Grey Square), 'Water Bottle' (Blue), 'Big Plate' (Large brown circle, 2-boxes wide).
3. The arm is HIDDEN in the image for clarity.
4. your outputs are limited to: 

{goto_coordinate = column, row}
{pickup}
{keep}
{Task_Completed}

4. Output step-by-step ONLY next command ONLY:
{goto_coordinate = column, row}

or 
{pickup}

or
{keep}

or
{Task_Completed}




but only one command at a time. Wait for the next image and instructions after each command."""

        self.chat_history = [{"role": "system", "content": system_prompt}]
        self.command_queue = []
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(self.process_queue)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        self.sim = RobotSim()
        layout.addWidget(self.sim, 7)

        right_side = QWidget()
        right_side.setStyleSheet("background: #0e0e1a; border-left: 2px solid #333;")
        right_layout = QVBoxLayout(right_side)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background: #0e0e1a; color: #e0e0e0; border: none; font-size: 14px;")
        self.chat_input = QLineEdit()
        self.chat_input.setStyleSheet("background: #1e1e2e; color: white; padding: 10px;")
        self.chat_input.returnPressed.connect(self.send_chat)
        
        right_layout.addWidget(QLabel("<h2 style='color:white;'>Autonomous Planner</h2>"))
        right_layout.addWidget(self.chat_display)
        right_layout.addWidget(self.chat_input)
        layout.addWidget(right_side, 3)

    def send_chat(self):
        txt = self.chat_input.text().strip()
        if not txt or self.execution_timer.isActive(): return
        self.sim.arm_visible = False
        self.sim.update()
        QApplication.processEvents()
        pixmap = self.sim.grab()
        self.sim.arm_visible = True
        
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        img_str = base64.b64encode(buffer.data().data()).decode("utf-8")
        
        self.chat_display.append(f"<b style='color:#4da6ff;'>Task:</b> {txt}")
        self.chat_input.clear()
        self.chat_input.setDisabled(True)
        self.chat_history.append({"role": "user", "content": txt})
        
        self.worker = ChatWorker(self.api_key, self.chat_history, img_str)
        self.worker.response_received.connect(self.handle_ai)
        self.worker.start()

    def handle_ai(self, response):
        self.chat_display.append(f"<br><div style='color:#00ff96;'>{response}</div>")
        self.chat_history.append({"role": "assistant", "content": response})
        self.command_queue = re.findall(r'\{(.*?)\}', response)
        self.execution_timer.start(800)

    def process_queue(self):
        if not self.command_queue:
            self.execution_timer.stop()
            self.chat_input.setDisabled(False)
            return
        if not self.sim.is_at_target(): return

        cmd = self.command_queue.pop(0).strip()
        if "goto_coordinate =" in cmd:
            parts = cmd.split('=')[1].split(',')
            coords = self.sim.get_coords(parts[0], parts[1])
            if coords: self.sim.bot_target = list(coords)
        elif cmd == "pickup":
            all_objs = [{"pos": self.sim.brick_pos, "ref": "brick"}] + [{"pos": o["pos"], "ref": o} for o in self.sim.extra_objects]
            for obj in all_objs:
                if math.hypot(self.sim.bot_pos[0]-obj["pos"][0], self.sim.bot_pos[1]-obj["pos"][1]) < 80:
                    self.sim.holding, self.sim.held_extra = True, obj["ref"]
                    break
        elif cmd == "keep": self.sim.holding, self.sim.held_extra = False, None
        elif cmd == "Task_Completed": self.command_queue = []

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
