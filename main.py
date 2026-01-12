
import os
from taipy.gui import Gui
from math import cos, exp

value = 10

def compute_data(decay: int) -> list[float]:
    return [cos(i/6) * exp(-i * decay / 600) for i in range(100)]

def slider_moved(state):
    state.data = compute_data(state.value)

data = compute_data(value)

page = """
# Welkom bij deze geweldige grafiek*

Value: <|{value}|text|>

<|{value}|slider|on_change=slider_moved|>

<|{data}|chart|>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    Gui(page).run(host="0.0.0.0", port=port, use_reloader=False)
