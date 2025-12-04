"""
Material Library Management
===========================
This module handles loading, parsing, and interpolating material properties.

Why is this file needed?
------------------------
1. Hierarchy: It merges 'System Defaults' (Read-only JSON) with 'User Custom'
   (Read/Write JSON) materials.
2. Physics: It converts raw data (tables or formulas) into callable methods
   (e.g., get_conductivity(T)) that the solver can use efficiently.
3. Vectorization: It uses 'numexpr' or 'numpy' to calculate properties for
   thousands of FEM nodes instantly.
"""
