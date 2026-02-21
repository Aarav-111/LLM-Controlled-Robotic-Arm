import sys
import math
import base64
import re
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QTextEdit, QPushButton, QLabel
from PySide6.QtCore import QTimer, Qt, QThread, Signal, QBuffer, QIODevice, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from openai import OpenAI

class ChatWorker(QThread):
    response_received = Signal(str)

    def __init__(self, api_key, history, image_base64=None):
        super().__init__()
        self.client = OpenAI(api_key=api_key)
        self.history = history
        self.image_base64 = image_base64

    def run(self):
        try:
            messages = []
            for msg in self.history:
                messages.append(msg)
            
            if self.image_base64:
                last_msg = messages[-1]
                if last_msg["role"] == "user":
                    text_content = last_msg["content"]
                    messages[-1]["content"] = [
                        {"type": "text", "text": text_content},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{self.image_base64}",
                                "detail": "high"
                            }
                        }
                    ]

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=500,
                temperature=0
            )
            reply = response.choices[0].message.content
            self.response_received.emit(reply)
        except Exception as e:
            self.response_received.emit(f"OpenAI Error: {str(e)}")

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
        
        self.extra_objects = [
            {"name": "Grey Box", "pos": [self.MARGIN_X + 120, self.MARGIN_Y - 80], "color": QColor(100, 100, 100), "type": "rect", "w": 40, "h": 40},
            {"name": "Water Bottle", "pos": [self.MARGIN_X + 200, self.MARGIN_Y - 80], "color": QColor(100, 150, 255), "type": "bottle", "w": 30, "h": 50}
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
        except:
            return None

    def update_physics(self):
        if self.dragging_obj:
            return
            
        dx = self.bot_target[0] - self.bot_pos[0]
        dy = self.bot_target[1] - self.bot_pos[1]
        dist = math.hypot(dx, dy)
        if dist > self.speed:
            self.bot_pos[0] += (dx / dist) * self.speed
            self.bot_pos[1] += (dy / dist) * self.speed
        else:
            self.bot_pos = list(self.bot_target)
            
        if self.holding:
            if self.held_extra == "brick":
                self.brick_pos = list(self.bot_pos)
            elif self.held_extra:
                self.held_extra["pos"] = list(self.bot_pos)
        self.update()

    def is_at_target(self):
        return math.hypot(self.bot_target[0] - self.bot_pos[0], self.bot_target[1] - self.bot_pos[1]) < 2

    def mousePressEvent(self, event):
        p = event.position().toPoint()
        if math.hypot(p.x() - self.bot_pos[0], p.y() - self.bot_pos[1]) < 40:
            self.dragging_obj = "bot"
            self.drag_offset = QPoint(p.x() - self.bot_pos[0], p.y() - self.bot_pos[1])
            return
        if abs(p.x() - self.brick_pos[0]) < 25 and abs(p.y() - self.brick_pos[1]) < 25:
            self.dragging_obj = "brick"
            self.drag_offset = QPoint(p.x() - self.brick_pos[0], p.y() - self.brick_pos[1])
            return
        for obj in self.extra_objects:
            if abs(p.x() - obj["pos"][0]) < obj["w"]/2 + 10 and abs(p.y() - obj["pos"][1]) < obj["h"]/2 + 10:
                self.dragging_obj = obj
                self.drag_offset = QPoint(p.x() - obj["pos"][0], p.y() - obj["pos"][1])
                return

    def mouseMoveEvent(self, event):
        if self.dragging_obj:
            p = event.position().toPoint()
            new_x = p.x() - self.drag_offset.x()
            new_y = p.y() - self.drag_offset.y()
            if self.dragging_obj == "bot":
                self.bot_pos = [new_x, new_y]
                self.bot_target = list(self.bot_pos)
            elif self.dragging_obj == "brick":
                self.brick_pos = [new_x, new_y]
            else:
                self.dragging_obj["pos"] = [new_x, new_y]
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging_obj = None

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        qp.fillRect(self.rect(), QColor(10, 10, 20))
        
        qp.setPen(QColor(60, 60, 80))
        qp.drawRect(self.MARGIN_X, self.MARGIN_Y - 110, 400, 90)
        qp.setPen(QColor(150, 150, 150))
        qp.setFont(QFont("Arial", 10))
        qp.drawText(self.MARGIN_X + 10, self.MARGIN_Y - 90, "STAGING AREA / SHELF")

        for c in range(8):
            for r in range(5):
                x = self.MARGIN_X + c * self.CELL_SIZE
                y = self.MARGIN_Y + r * self.CELL_SIZE
                qp.setPen(QColor(40, 45, 60))
                qp.drawRect(x, y, self.CELL_SIZE, self.CELL_SIZE)
                
                qp.setPen(QColor(60, 60, 80))
                cell_label = f"{self.COL_LABELS[c]}{self.ROW_LABELS[4-r]}"
                qp.drawText(x + 5, y + 20, cell_label)

        qp.setPen(QColor(0, 180, 255))
        qp.setFont(QFont("Courier New", 12, QFont.Bold))
        for i, lbl in enumerate(self.COL_LABELS):
            qp.drawText(self.MARGIN_X + i * self.CELL_SIZE + 35, self.MARGIN_Y + (5*self.CELL_SIZE) + 25, lbl)
        for i, lbl in enumerate(reversed(self.ROW_LABELS)):
            qp.drawText(self.MARGIN_X - 25, self.MARGIN_Y + i * self.CELL_SIZE + 45, lbl)

        def draw_obj(obj_type, x, y, w, h, color):
            qp.setBrush(color)
            qp.setPen(Qt.NoPen)
            if obj_type == "rect":
                qp.drawRect(int(x - w/2), int(y - h/2), w, h)
            elif obj_type == "bottle":
                qp.drawRoundedRect(int(x - w/2), int(y - h/2), w, h, 5, 5)
                qp.drawRect(int(x - w/4), int(y - h/2 - 5), int(w/2), 5)

        for obj in self.extra_objects:
            draw_obj(obj["type"], obj["pos"][0], obj["pos"][1], obj["w"], obj["h"], obj["color"])
        
        draw_obj("rect", self.brick_pos[0], self.brick_pos[1], 40, 40, QColor(240, 240, 240))

        if self.arm_visible:
            grid_top = self.MARGIN_Y
            grid_bottom = self.MARGIN_Y + (5 * self.CELL_SIZE)
            grid_left = self.MARGIN_X
            grid_right = self.MARGIN_X + (8 * self.CELL_SIZE)

            qp.setPen(QPen(QColor(50, 50, 60), 10))
            qp.drawLine(grid_left - 20, grid_top - 10, grid_right + 20, grid_top - 10)
            qp.drawLine(grid_left - 20, grid_bottom + 10, grid_right + 20, grid_bottom + 10)

            rail_x = self.bot_pos[0]
            qp.setPen(QPen(QColor(40, 100, 140), 14))
            qp.drawLine(int(rail_x), int(grid_top - 10), int(rail_x), int(grid_bottom + 10))
            qp.setPen(QPen(QColor(100, 200, 255), 2))
            qp.drawLine(int(rail_x), int(grid_top - 10), int(rail_x), int(grid_bottom + 10))

            head_y = self.bot_pos[1]
            qp.setBrush(QColor(30, 30, 30))
            qp.setPen(QPen(QColor(255, 140, 0), 2))
            qp.drawRect(int(rail_x - 25), int(head_y - 25), 50, 50)
            qp.setBrush(QColor(255, 140, 0))
            qp.setPen(Qt.NoPen)
            qp.drawEllipse(int(rail_x - 8), int(head_y - 8), 16, 16)

            qp.setPen(QPen(QColor(200, 200, 200), 4))
            claw_offset = 10 if self.holding else 25 
            qp.drawLine(int(rail_x - 15), int(head_y + 25), int(rail_x - 15), int(head_y + 40))
            qp.drawLine(int(rail_x - 15), int(head_y + 40), int(rail_x - claw_offset), int(head_y + 50))
            qp.drawLine(int(rail_x + 15), int(head_y + 25), int(rail_x + 15), int(head_y + 40))
            qp.drawLine(int(rail_x + 15), int(head_y + 40), int(rail_x + claw_offset), int(head_y + 50))
        
        qp.end()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prolabs V12.2 - Precision Cartesian Gantry")
        self.showMaximized() 
        
        self.api_key = "YOUR OPENAI API KEY HERE"
        
        system_prompt = """You are a Coordinate locator & planner for a Cartesian Gantry Robot.
IMAGE ANALYSIS RULES:
1. Identify the grid labels (A-H columns, 1-5 rows).
2. Locate the requested object precisely.
3. The 'White Brick' is a white square. The 'Grey Box' is grey. The 'Water Bottle' is blue.
4. NOTE: In the image provided, the robotic arm is HIDDEN so you can see the grid clearly.

TASK RULES:
Output step-by-step commands using ONLY these tags:
{goto_coordinate = column, row}
{pickup}
{keep}
{Task_Completed}

IMPORTANT: Look closely at the grid. If an object is in the 3rd column from the left, it is 'C'. If it is in the top row, it is '5'. 
Example: Move white brick to E3.
{goto_coordinate = A, 3}
{pickup}
{goto_coordinate = E, 3}
{keep}
{Task_Completed}"""

        self.chat_history = [{"role": "system", "content": system_prompt}]
        self.command_queue = []
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(self.process_queue)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left_side = QWidget()
        left_layout = QVBoxLayout(left_side)
        self.sim = RobotSim()
        left_layout.addWidget(self.sim)

        right_side = QWidget()
        right_side.setStyleSheet("background-color: #0e0e1a; border-left: 2px solid #333;")
        right_layout = QVBoxLayout(right_side)
        right_layout.setContentsMargins(20, 20, 20, 20)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background: #0e0e1a; color: #e0e0e0; font-family: Segoe UI; font-size: 14px; border: none;")
        self.chat_display.append("<b>Prolabs AI:</b> Cartesian System Ready. Describe a movement task.<br>")

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Describe task (e.g., 'Place bottle at B2')...")
        self.chat_input.setStyleSheet("background: #1e1e2e; color: white; padding: 12px; border-radius: 5px; font-size: 14px; border: 1px solid #444;")
        self.chat_input.returnPressed.connect(self.send_chat)

        self.send_btn = QPushButton("Execute")
        self.send_btn.setStyleSheet("""
            QPushButton { background-color: #007acc; color: white; padding: 10px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #005f9e; }
        """)
        self.send_btn.clicked.connect(self.send_chat)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_btn)

        right_layout.addWidget(QLabel("<h2 style='color:white;'>Autonomous Planner</h2>"))
        right_layout.addWidget(self.chat_display)
        right_layout.addLayout(input_layout)

        layout.addWidget(left_side, 7)
        layout.addWidget(right_side, 3)

    def capture_board(self):
        self.sim.arm_visible = False
        pixmap = self.sim.grab()
        self.sim.arm_visible = True
        
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        return base64.b64encode(buffer.data().data()).decode("utf-8")

    def send_chat(self):
        user_text = self.chat_input.text().strip()
        if not user_text or self.execution_timer.isActive():
            return
        
        image_data = self.capture_board()
        self.chat_display.append(f"<div style='color: #4da6ff;'><b>Task:</b> {user_text}</div>")
        self.chat_input.clear()
        self.chat_input.setDisabled(True)
        self.chat_history.append({"role": "user", "content": user_text})

        self.worker = ChatWorker(self.api_key, self.chat_history, image_data)
        self.worker.response_received.connect(self.handle_ai_response)
        self.worker.start()

    def handle_ai_response(self, response):
        self.chat_display.append(f"<br><div style='color: #00ff96;'>{response}</div><br>")
        self.chat_history.append({"role": "assistant", "content": response})
        
        commands = re.findall(r'\{(.*?)\}', response)
        self.command_queue = commands
        self.execution_timer.start(800)

    def process_queue(self):
        if not self.command_queue:
            self.execution_timer.stop()
            self.chat_input.setDisabled(False)
            self.chat_input.setFocus()
            return

        if not self.sim.is_at_target():
            return

        cmd = self.command_queue.pop(0).strip()

        if "goto_coordinate =" in cmd:
            parts = cmd.split('=')[1].split(',')
            if len(parts) == 2:
                coords = self.sim.get_coords(parts[0], parts[1])
                if coords:
                    self.sim.bot_target = list(coords)
        elif cmd == "pickup":
            all_objs = [{"pos": self.sim.brick_pos, "ref": "brick"}] + [{"pos": o["pos"], "ref": o} for o in self.sim.extra_objects]
            found = False
            for obj in all_objs:
                dist = math.hypot(self.sim.bot_pos[0] - obj["pos"][0], self.sim.bot_pos[1] - obj["pos"][1])
                if dist < 60: 
                    self.sim.holding = True
                    self.sim.held_extra = obj["ref"]
                    found = True
                    break
        elif cmd == "keep":
            self.sim.holding = False
            self.sim.held_extra = None
        elif cmd == "Task_Completed":
            self.command_queue = []

        sb = self.chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show() 
    sys.exit(app.exec())
