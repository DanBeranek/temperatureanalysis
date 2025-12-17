"""
FEM Solver Engine
=================
The core implementation for the temperature analysis.

Why is this file needed?
------------------------
1. Physics: It implements the mathematical equations (Heat Equation, Fire Curves).
2. Time-Stepping: It manages the temporal loop (t=0 to t=End).
3. Data Generation: It calculates the node temperatures and sends them to the
   IO Manager for storage.

Note: This module should be pure Python/NumPy and should NOT import PySide6.
"""
