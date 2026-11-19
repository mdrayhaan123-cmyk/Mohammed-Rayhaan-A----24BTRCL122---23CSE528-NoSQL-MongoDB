"""Entrypoint script inside the Docker container to demonstrate all Lab 9 tasks."""

import os
import runpy

ROOT = os.path.dirname(os.path.abspath(__file__))

for rel in [
    "Lab_9_1/lab_9_1.py",
    "Lab_9_1_Try_It_Yourself/lab_9_1_try_it_yourself.py",
    "Lab_9_2/lab_9_2.py",
]:
    runpy.run_path(os.path.join(ROOT, rel), run_name="__main__")
