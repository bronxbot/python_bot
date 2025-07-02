#!/usr/bin/env python3

import subprocess
import re

# Test the journal parsing directly
def test_stats_parsing():
    try:
        print("Testing journal parsing...")
        journal_result = subprocess.run([
            'journalctl', '--user', '-u', 'bronxbot', 
            '--since', '10 minutes ago', '--no-pager'
        ], capture_output=True, text=True, timeout=10)
        
        if journal_result.returncode == 0:
            journal_lines = journal_result.stdout.split('\n')
            print(f"Found {len(journal_lines)} journal lines")
            
            guilds = 0
            users = 0
            latency = 0
            
            for line in reversed(journal_lines[-100:]):
                if 'Events:' in line and 'Guilds:' in line and 'Users:' in line:
                    print(f"Found stats line: {line.strip()}")
                    
                    # Parse using the split method
                    parts = line.split('|')
                    for part in parts:
                        part = part.strip()
                        if 'Guilds:' in part:
                            guild_nums = re.findall(r'\d+', part)
                            if guild_nums:
                                guilds = int(guild_nums[0])
                                print(f"Parsed guilds: {guilds}")
                        elif 'Users:' in part:
                            user_nums = re.findall(r'\d+', part)
                            if user_nums:
                                users = int(user_nums[0])
                                print(f"Parsed users: {users}")
                        elif 'Latency:' in part:
                            lat_nums = re.findall(r'\d+', part)
                            if lat_nums:
                                latency = int(lat_nums[0])
                                print(f"Parsed latency: {latency}")
                    break
            
            print(f"Final parsed stats: Guilds={guilds}, Users={users}, Latency={latency}")
            
        else:
            print(f"Journal command failed with code: {journal_result.returncode}")
            print(f"Error: {journal_result.stderr}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_stats_parsing()
