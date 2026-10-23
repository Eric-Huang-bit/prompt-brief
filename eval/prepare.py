"""Materialize immutable eval fixtures and blind task manifests; no model calls."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--cases', type=Path, default=Path(__file__).with_name('cases.jsonl'))
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    root = args.run.resolve()
    if args.verify:
        before = json.loads((root / 'snapshot.json').read_text(encoding='utf-8'))
        after = snapshot(root / 'fixtures')
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        print(json.dumps({'unchanged': not changed, 'changed': changed}, ensure_ascii=False))
        raise SystemExit(1 if changed else 0)
    cases = [json.loads(s) for s in args.cases.read_text(encoding='utf-8').splitlines() if s.strip()]
    ids = [c['id'] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case IDs')
    # Validate every path before writing; both POSIX and Windows traversal matter.
    for case in cases:
        if not case['id'].isdigit():
            raise ValueError('Non-numeric case ID')
        for name in case['files']:
            win = PureWindowsPath(name)
            if win.is_absolute() or win.drive or '..' in win.parts or ':' in name:
                raise ValueError(f'Unsafe fixture path: {name}')
            target = (root / 'fixtures' / case['id'] / name).resolve()
            if not target.is_relative_to(root / 'fixtures' / case['id']):
                raise ValueError(f'Fixture escape: {name}')
    root.mkdir(parents=True, exist_ok=False)
    tasks = []
    for case in cases:
        project = root / 'fixtures' / case['id']
        project.mkdir(parents=True)
        for name, content in case['files'].items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        tasks.append({'id': case['id'], 'request': case['request'], 'project': str(project)})
    (root / 'tasks.json').write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'snapshot.json').write_text(json.dumps(snapshot(root / 'fixtures'), indent=2), encoding='utf-8')
    (root / 'outputs').mkdir()
    print(f'Prepared {len(tasks)} cases at {root}')


if __name__ == '__main__':
    main()
