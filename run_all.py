#!/usr/bin/env python3
"""
Batch downloader — runs all targets from targets.json in parallel tmux sessions.
Mounts Google Drive via rclone and writes directly to it.

Usage:
    python3 run_all.py              # запустить все таргеты
    python3 run_all.py --status     # показать статус всех сессий
    python3 run_all.py --stop       # остановить все сессии
    python3 run_all.py --only NAME  # запустить только один таргет
"""

import json
import os
import subprocess
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(SCRIPT_DIR, 'targets.json')
MOUNT_POINT = '/mnt/gdrive'


def load_config():
    with open(TARGETS_FILE) as f:
        return json.load(f)


def ensure_gdrive_mounted():
    """Mount Google Drive if not already mounted."""
    from cloud_sync import GDriveMount
    mount = GDriveMount(mount_point=MOUNT_POINT)
    if mount.is_mounted():
        print(f"  GDrive already mounted at {MOUNT_POINT}")
        return True
    print(f"  Mounting GDrive at {MOUNT_POINT}...")
    if mount.mount():
        print(f"  GDrive mounted OK")
        return True
    print(f"  ERROR: Failed to mount GDrive")
    return False


def run_all(config, only=None):
    """Launch each target in a separate tmux session."""
    if not ensure_gdrive_mounted():
        print("\nAborted: Google Drive mount failed.")
        return
    
    targets = config['targets']
    if only:
        targets = [t for t in targets if t['name'] == only]
        if not targets:
            print(f"  Target '{only}' not found in targets.json")
            return
    
    for target in targets:
        name = target['name']
        session_name = f"dl-{name}"
        output_dir = name
        log_file = os.path.join('/tmp', f"tor-{name}.log")
        
        # Check if session already exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', session_name],
            capture_output=True
        )
        if result.returncode == 0:
            print(f"  [{name}] already running — skipping")
            continue
        
        cmd = (
            f"cd {SCRIPT_DIR} && python3 cli.py "
            f'"{target["url"]}" '
            f"-o {output_dir} "
            f"--site-type {target['site_type']} "
            f"--mount-gdrive "
        )
        
        if target.get('password'):
            cmd += f"--password \"{target['password']}\" "
        
        if target.get('max_depth'):
            cmd += f"--max-depth {target['max_depth']} "
        
        cmd += f"2>&1 | tee {log_file}"
        
        subprocess.run([
            'tmux', 'new-session', '-d', '-s', session_name, cmd
        ])
        print(f"  [{name}] started -> {MOUNT_POINT}/{output_dir}")
        print(f"           tmux attach -t {session_name}")
    
    print()
    print("Commands:")
    print("  tmux ls                          — list sessions")
    print("  tmux attach -t dl-<name>         — attach to session")
    print("  python3 run_all.py --status      — check progress")
    print("  python3 run_all.py --stop        — stop all")


def show_status(config):
    """Show status of all download sessions."""
    for target in config['targets']:
        name = target['name']
        session_name = f"dl-{name}"
        log_file = f"/tmp/tor-{name}.log"
        
        # Check if session is running
        result = subprocess.run(
            ['tmux', 'has-session', '-t', session_name],
            capture_output=True
        )
        running = result.returncode == 0
        
        status = "RUNNING" if running else "STOPPED"
        
        # Get last line of log
        last_line = ""
        if os.path.exists(log_file):
            try:
                result = subprocess.run(
                    ['tail', '-1', log_file],
                    capture_output=True, text=True
                )
                last_line = result.stdout.strip()[:100]
            except:
                pass
        
        print(f"  [{status:7}] {name}")
        if last_line:
            print(f"           {last_line}")
        print()


def stop_all(config):
    """Stop all download sessions."""
    for target in config['targets']:
        name = target['name']
        session_name = f"dl-{name}"
        subprocess.run(
            ['tmux', 'kill-session', '-t', session_name],
            capture_output=True
        )
        print(f"  [{name}] stopped")


def main():
    parser = argparse.ArgumentParser(description='Batch Tor downloader')
    parser.add_argument('--status', action='store_true', help='Show status of all sessions')
    parser.add_argument('--stop', action='store_true', help='Stop all sessions')
    parser.add_argument('--only', default=None, help='Run only specific target by name')
    args = parser.parse_args()
    
    config = load_config()
    
    if args.status:
        show_status(config)
    elif args.stop:
        stop_all(config)
    else:
        # Kill existing sessions for targets we're about to start
        targets = config['targets']
        if args.only:
            targets = [t for t in targets if t['name'] == args.only]
        for target in targets:
            subprocess.run(
                ['tmux', 'kill-session', '-t', f"dl-{target['name']}"],
                capture_output=True
            )
        run_all(config, only=args.only)


if __name__ == '__main__':
    main()
