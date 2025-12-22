import os
import re
import sys
import subprocess
import argparse

# Directory to scan
UI_DIR = "ui"
# File extensions to check
EXTENSIONS = [".css", ".html"]

# Regex to find font-size declarations
# This regex looks for font-size: followed by a value until a semicolon, closing quote, or end of line.
# It captures the value itself.
FONT_SIZE_REGEX = re.compile(r'font-size\s*:\s*([^;!"\'>\s]+)', re.IGNORECASE)

# Allowed values that are not var()
# We allow '0' because font-size: 0 is sometimes used for layout hacks, 
# though variables are still preferred.
ALLOWED_VALUES = {"inherit", "initial", "unset", "revert", "0"}

def get_changed_files(repo_root, staged_only=False):
    """Get a list of changed or staged files in the ui directory."""
    try:
        # Get staged files
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], 
            cwd=repo_root, 
            text=True
        ).splitlines()
        
        if staged_only:
            changed_files = staged
        else:
            # Get unstaged files
            unstaged = subprocess.check_output(
                ["git", "diff", "--name-only"], 
                cwd=repo_root, 
                text=True
            ).splitlines()
            # Combine and deduplicate
            changed_files = list(set(staged + unstaged))
        
        # Filter by directory and extension
        filtered_files = []
        for f in changed_files:
            if f.startswith(UI_DIR) and any(f.endswith(ext) for ext in EXTENSIONS):
                # Ensure the file still exists (it might have been deleted)
                full_path = os.path.join(repo_root, f)
                if os.path.exists(full_path):
                    filtered_files.append(full_path)
        
        return filtered_files
    except subprocess.CalledProcessError:
        # Not a git repo or git not installed
        return []

def check_file(filepath):
    violations = []
    if not os.path.exists(filepath):
        return violations
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Skip comments in CSS if possible, but for a simple check we can just grep
                if line.strip().startswith("/*") or line.strip().startswith("*") or line.strip().endswith("*/"):
                    # This is a very basic comment skip, could be improved
                    if "font-size" not in line:
                        continue
                
                matches = FONT_SIZE_REGEX.finditer(line)
                for match in matches:
                    value = match.group(1).strip()
                    
                    # Normalize value: remove any trailing spaces or !important-related chars if they leaked in
                    value = value.split('!')[0].strip()
                    
                    # Check if it's a variable or an allowed keyword
                    if not (value.startswith("var(") or value.lower() in ALLOWED_VALUES):
                        violations.append((i + 1, match.group(0).strip()))
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return violations

def main():
    parser = argparse.ArgumentParser(description="Check for hardcoded font-size values.")
    parser.add_argument("--all", action="store_true", help="Check all files in the ui directory.")
    parser.add_argument("--staged", action="store_true", help="Check only staged files.")
    args = parser.parse_args()

    all_violations = {}
    
    # Get the repository root directory to ensure paths are correct
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(repo_root, UI_DIR)
    
    if not os.path.exists(target_dir):
        print(f"Directory not found: {target_dir}")
        sys.exit(0)

    files_to_check = []
    
    if args.all:
        print("Scanning all files in ui/ directory...")
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if any(file.endswith(ext) for ext in EXTENSIONS):
                    files_to_check.append(os.path.join(root, file))
    else:
        files_to_check = get_changed_files(repo_root, staged_only=args.staged)
        if not files_to_check:
            mode = "staged " if args.staged else "changed "
            print(f"\033[92m✅ No {mode}CSS/HTML files to check.\033[0m")
            sys.exit(0)
        
        mode = "staged" if args.staged else "changed"
        print(f"Scanning {len(files_to_check)} {mode} file(s)...")

    # Check the identified files
    for filepath in files_to_check:
        violations = check_file(filepath)
        if violations:
            # Store relative path for cleaner output
            rel_path = os.path.relpath(filepath, repo_root)
            all_violations[rel_path] = violations

    if all_violations:
        print("\033[91m❌ Found hardcoded font-size values in your changes!\033[0m")
        print("Best practice: use var(--font-size-*) variables defined in base.css")
        print("-" * 80)
        for filepath, violations in all_violations.items():
            print(f"File: \033[1m{filepath}\033[0m")
            for line_num, content in violations:
                print(f"  Line {line_num:4}: {content}")
        print("-" * 80)
        print(f"Found {sum(len(v) for v in all_violations.values())} violations in {len(all_violations)} files.")
        print("Please fix these before committing or use 'git commit --no-verify' if absolutely necessary.")
        sys.exit(1)
    else:
        print("\033[92m✅ Font-size check passed for changed files!\033[0m")
        sys.exit(0)

if __name__ == "__main__":
    main()

