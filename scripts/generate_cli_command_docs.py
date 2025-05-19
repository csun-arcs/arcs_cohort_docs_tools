#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path
import re

def parse_args():
    parser = argparse.ArgumentParser(description="Generate Markdown documentation for CLI tools.")
    parser.add_argument("--command", type=str, required=True,
                        help="Top-level CLI command (e.g., arcscfg, ros2, etc.)")
    parser.add_argument("--output", type=Path, default=Path("cli_docs"),
                        help="Directory to save generated markdown files.")
    parser.add_argument("--name", type=str, default=None,
                        help="Optional override name for the top-level markdown file.")
    parser.add_argument("--title", type=str, default=None,
                        help="Optional title for the top-level markdown file.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print output instead of writing files.")
    return parser.parse_args()

def run_help(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"[ERROR] Failed to run {' '.join(cmd)}:\n{e.stderr.strip()}"

def extract_subcommands(help_output):
    lines = help_output.splitlines()
    commands_section = False
    cmd_block = ""
    for i, line in enumerate(lines):
        if "Available commands" in line:
            commands_section = True
        if commands_section and re.match(r"\s*{.*}", line):
            cmd_block = line
            break
    match = re.search(r"{([^}]+)}", cmd_block)
    if not match:
        return []
    return [cmd.strip() for cmd in match.group(1).split(",")]

def write_markdown(path, title, content, dry_run=False):
    md = f"# {title}\n\n```{content}```"
    if dry_run:
        print(f"[DRY RUN] Would write: {path}")
        print(md)
    else:
        path.write_text(md)
        print(f"[INFO] Wrote: {path}")

def main():
    args = parse_args()

    base_dir = args.output.resolve()
    if not args.dry_run:
        base_dir.mkdir(parents=True, exist_ok=True)

    tool = args.command
    top_name = args.name or tool
    title = args.title or f"{tool} CLI"
    top_help = run_help([tool, "-h"])
    top_path = base_dir / f"{top_name}.md"
    write_markdown(top_path, title, top_help, dry_run=args.dry_run)

    subcommands = extract_subcommands(top_help)
    print(f"[INFO] Found {len(subcommands)} subcommand(s): {', '.join(subcommands)}")

    for sub in subcommands:
        sub_help = run_help([tool, sub, "-h"])
        sub_path = base_dir / f"{top_name}_{sub}.md"
        write_markdown(sub_path, f"{tool} {sub}", sub_help, dry_run=args.dry_run)

    print(f"[INFO] CLI documentation {'simulated' if args.dry_run else 'generated'} in: {base_dir}")

if __name__ == "__main__":
    main()
