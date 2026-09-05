#!/usr/bin/env python3
"""Remove a named task worktree only after local integration and preservation."""
import argparse
from pathlib import Path
import subprocess
import sys


def remove(repo, worktree, branch, integration):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    repo, worktree = repo.resolve(), worktree.resolve()
    records = git('worktree', 'list', '--porcelain').split('\n\n')
    owned = any(f'worktree {worktree}\n' in record + '\n' and
                f'branch refs/heads/{branch}\n' in record + '\n' for record in records)
    if not owned or branch == integration or worktree == repo:
        raise ValueError('worktree/branch ownership does not match the explicit task target')
    # Include ignored artifacts: a handoff does not become disposable because git ignores it.
    status = git('-C', str(worktree), 'status', '--porcelain', '--untracked-files=all', '--ignored')
    if status:
        raise ValueError('dirty, untracked or ignored artifacts remain; preserve them first')
    if git('merge-base', branch, integration) != git('rev-parse', branch):
        raise ValueError('task commits are not integrated into the selected integration branch')
    subprocess.run(['git', '-C', str(repo), 'worktree', 'remove', str(worktree)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--worktree', type=Path, required=True)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--integration', required=True)
    args = parser.parse_args()
    try:
        remove(args.repo, args.worktree, args.branch, args.integration)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'BLOCKED: unsafe worktree cleanup\nWHY: {error}\nFIX: git -C {str(args.worktree)!r} status --short --ignored', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
