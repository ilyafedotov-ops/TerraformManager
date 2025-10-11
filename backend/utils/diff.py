from difflib import unified_diff

def make_unified_diff(before: str, after: str, filename: str) -> str:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = unified_diff(before_lines, after_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}")
    return "".join(diff)
