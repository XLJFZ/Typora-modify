"""Check local CSS imports, including transitive dependencies."""
import re
from pathlib import Path


def imports(source):
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    return re.findall(r'''@import\s+(?:url\(\s*)?["']([^"']+)["']''', source, re.I)


def check_imports(css, allow_missing_night=False):
    missing, skipped, visited = [], [], set()

    def visit(path):
        path = Path(path).resolve()
        if path in visited:
            return
        visited.add(path)
        for target in imports(path.read_text(encoding='utf-8')):
            dependency = path.parent / target
            if not dependency.is_file():
                if allow_missing_night and target.startswith('night/'):
                    skipped.append(str(dependency))
                else:
                    missing.append(str(dependency))
            else:
                visit(dependency)

    visit(css)
    return missing, skipped
