#!/usr/bin/env python3
"""
Test application for AIVory Monitor breakpoint testing.
Run this app, then set breakpoints in the IDE on the functions below.
"""

import sys
import time
import random

sys.path.insert(0, '.')
import aivory_monitor

# Initialize agent
aivory_monitor.init(
    api_key='aiv_mon_3c81a299de5f4ebfa9219e6a',
    backend_url='ws://localhost:8080/ws/monitor/agent',
    environment='development',
    debug=True,
)

print("\n" + "="*60)
print("AIVory Monitor Test App - Set breakpoints on these functions:")
print("  - process_user()       line 35")
print("  - calculate_total()    line 45")
print("  - fetch_data()         line 55")
print("Press Ctrl+C to stop.")
print("="*60 + "\n")

time.sleep(2)


def process_user(user_id: int) -> dict:
    """Set breakpoint here - line 35"""
    user_data = {
        'id': user_id,
        'name': f'User_{user_id}',
        'email': f'user{user_id}@example.com',
        'active': user_id % 2 == 0
    }
    return user_data


def calculate_total(items: list) -> float:
    """Set breakpoint here - line 45"""
    total = 0.0
    for item in items:
        price = item.get('price', 0)
        quantity = item.get('quantity', 1)
        total += price * quantity
    return total


def fetch_data(query: str) -> list:
    """Set breakpoint here - line 55"""
    results = []
    for i in range(random.randint(1, 5)):
        results.append({'id': i, 'query': query, 'value': random.random() * 100})
    return results


iteration = 0
while True:
    iteration += 1
    print(f"\n[Iteration {iteration}]")

    user = process_user(random.randint(1, 100))
    print(f"  User: {user['name']}")

    items = [{'price': random.uniform(10, 50), 'quantity': random.randint(1, 5)}]
    total = calculate_total(items)
    print(f"  Total: ${total:.2f}")

    data = fetch_data(random.choice(['products', 'orders']))
    print(f"  Data: {len(data)} results")

    time.sleep(3)
