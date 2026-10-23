"""Exercise fixture isolation and mutation detection without a model API."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class PrepareTests(unittest.TestCase):
    def setUp(self):
        runs = Path(__file__).parent / 'runs'
        runs.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runs)
        self.base = Path(self.temp.name)
        self.script = self.base / 'prepare.py'
        shutil.copyfile(Path(__file__).with_name('prepare.py'), self.script)
        self.cases = self.base / 'cases.jsonl'
        self.run = self.base / 'run'

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, cases=None, verify=False):
        if cases is not None:
            self.cases.write_text('\n'.join(json.dumps(c, ensure_ascii=False) for c in cases), encoding='utf-8')
        return subprocess.run([sys.executable, '-X', 'utf8', str(self.script), str(self.run)]
                              + (['--verify'] if verify else []), capture_output=True, text=True, encoding='utf-8')

    def case(self, name='src/中文.txt'):
        return {'id': '01', 'request': '优化需求', 'files': {name: '中文内容'},
                'expected': ['must stay hidden'], 'fail_if': ['must stay hidden']}

    def test_unicode_and_blind_manifest(self):
        self.assertEqual(self.invoke([self.case()]).returncode, 0)
        self.assertEqual((self.run / 'fixtures/01/src/中文.txt').read_text(encoding='utf-8'), '中文内容')
        task = json.loads((self.run / 'tasks.json').read_text(encoding='utf-8'))[0]
        self.assertEqual(set(task), {'id', 'request', 'project'})
        self.assertEqual(self.invoke(verify=True).returncode, 0)

    def test_reject_path_escape(self):
        for name in ('../outside.txt', '..\\outside.txt', 'C:\\outside.txt', '/outside.txt', 'C:outside.txt', 'file:stream'):
            with self.subTest(name=name):
                self.assertNotEqual(self.invoke([self.case(name)]).returncode, 0)
                self.assertFalse(self.run.exists())

    def test_duplicate_id_rejected(self):
        self.assertNotEqual(self.invoke([self.case(), self.case()]).returncode, 0)
        self.assertFalse(self.run.exists())

    def test_existing_run_not_overwritten(self):
        self.assertEqual(self.invoke([self.case()]).returncode, 0)
        path = self.run / 'fixtures/01/src/中文.txt'
        path.write_text('keep', encoding='utf-8')
        self.assertNotEqual(self.invoke([self.case()]).returncode, 0)
        self.assertEqual(path.read_text(encoding='utf-8'), 'keep')

    def test_detect_modified_added_deleted(self):
        self.assertEqual(self.invoke([self.case()]).returncode, 0)
        path = self.run / 'fixtures/01/src/中文.txt'
        path.write_text('changed', encoding='utf-8')
        self.assertNotEqual(self.invoke(verify=True).returncode, 0)
        path.unlink()
        self.assertNotEqual(self.invoke(verify=True).returncode, 0)
        (path.parent / 'added.txt').write_text('added', encoding='utf-8')
        self.assertNotEqual(self.invoke(verify=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
