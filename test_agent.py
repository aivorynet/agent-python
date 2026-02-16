#!/usr/bin/env python3
"""Test script to start Python agent and trigger exceptions."""

import sys
import time

# Add the agent package to path
sys.path.insert(0, '.')

import aivory_monitor

# Initialize agent with local backend using REAL token from database
aivory_monitor.init(
    api_key='aiv_mon_3c81a299de5f4ebfa9219e6a',  # Real token for org test_20
    backend_url='ws://localhost:19999/ws/monitor/agent',
    environment='development',
    debug=True,
)

print("\n[Test] Agent initialized. Now triggering some exceptions...\n")

# Give time for connection
time.sleep(2)


def function_that_fails(user_id):
    """Simulate a function that throws an exception."""
    users = {"1": "Alice", "2": "Bob"}
    return users[user_id]  # Will throw KeyError for invalid ID


def process_request(data):
    """Simulate request processing."""
    result = data["value"] / data["divisor"]  # ZeroDivisionError if divisor=0
    return result


# Trigger exception 1: KeyError
print("[Test] Triggering KeyError...")
try:
    function_that_fails("999")
except Exception as e:
    aivory_monitor.capture_exception(e, context={"request_id": "req-001", "user_action": "get_user"})
    print(f"[Test] Captured: {type(e).__name__}: {e}")

time.sleep(1)

# Trigger exception 2: ZeroDivisionError
print("[Test] Triggering ZeroDivisionError...")
try:
    process_request({"value": 100, "divisor": 0})
except Exception as e:
    aivory_monitor.capture_exception(e, context={"request_id": "req-002", "endpoint": "/api/calculate"})
    print(f"[Test] Captured: {type(e).__name__}: {e}")

time.sleep(1)

# Trigger exception 3: AttributeError
print("[Test] Triggering AttributeError...")
try:
    obj = None
    obj.some_method()
except Exception as e:
    aivory_monitor.capture_exception(e, context={"request_id": "req-003", "component": "user_service"})
    print(f"[Test] Captured: {type(e).__name__}: {e}")

time.sleep(1)

# Trigger exception 4: ValueError
print("[Test] Triggering ValueError...")
try:
    int("not_a_number")
except Exception as e:
    aivory_monitor.capture_exception(e, context={"request_id": "req-004", "input_field": "age"})
    print(f"[Test] Captured: {type(e).__name__}: {e}")

print("\n[Test] Done! Keeping agent running for 30 seconds to ensure delivery...")
print("[Test] Check the JetBrains plugin - Exceptions and Agents tabs should show data.\n")

# Keep running for a bit to ensure messages are sent
time.sleep(30)

print("[Test] Shutting down agent...")
aivory_monitor.shutdown()
print("[Test] Complete!")
