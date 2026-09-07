import copy
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from unittest.mock import patch, Mock

import requests
import yaml

import agent_config as config
import agent_update as update
import esag_console as console
import essay_agent as agent

REPO = Path(__file__).resolve().parents[1]
FIELDS = ['中文摘要', '研究主题', '空间/场景类型', '研究场景', '自变量', '因变量', '行为指标',
          '生理/感知指标', '研究方法', '数据/样本', '主要结论', '与建筑/体育空间/疗愈环境研究相关性', '可借鉴启发']


def analysis(score=80):
    return {**{field: '未明确说明' for field in FIELDS}, '相关性分数': score}


def response(data, links=None):
    result = Mock(status_code=200, links=links or {})
    result.json.return_value = data
    return result


class TempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = config.profile_from_env({'OPENAI_API_KEY': 'test-secret', 'OPENAI_MODEL': 'model-a'})


class ConfigTests(TempCase):
    def test_env_preserves_special_characters_and_other_settings(self):
        file = self.root / '.env'
        file.write_text('# preserved\nDAYS_BACK=7\nOPENAI_API_KEY=old\nOPENAI_API_KEY=duplicate\n')
        secret = "quote' double\" slash\\ dollar${HOME} `uname` $(touch /tmp/bad) & | #"
        config.write_env(file, {'OPENAI_API_KEY': secret})
        self.assertEqual(config.read_env(file)['OPENAI_API_KEY'], secret)
        self.assertEqual(config.read_env(file)['DAYS_BACK'], '7')
        self.assertIn('# preserved', file.read_text())
        self.assertEqual(file.read_text().count('OPENAI_API_KEY='), 1)
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)

    def test_newline_rejected_without_modification(self):
        file = self.root / '.env'
        file.write_text('DAYS_BACK=7\n')
        with self.assertRaises(ValueError):
            config.write_env(file, {'KEY': 'secret\nINJECT=true'})
        self.assertEqual(file.read_text(), 'DAYS_BACK=7\n')

    def test_url_custom_path_preserved_and_endpoints_rejected(self):
        self.assertEqual(config.normalize_url(' https://host/api/custom/ '), 'https://host/api/custom')
        for url in ('ftp://host', 'https://host/v1/models', 'https://user:pass@host', 'https://host?q=key', 'https://host/v1/chat/completions'):
            with self.assertRaises(ValueError):
                config.normalize_url(url)

    def test_profile_migration_and_switch_preserve_old_interface(self):
        config.write_env(self.root / '.env', {'OPENAI_API_KEY': 'old-key', 'OPENAI_MODEL': 'old-model', 'DAYS_BACK': '9'})
        store = config.ProfileStore(self.root)
        self.assertEqual(store.active()['model'], 'old-model')
        draft = dict(self.profile, name='new')
        store.activate(draft)
        loaded = config.ProfileStore(self.root)
        self.assertEqual(loaded.active()['name'], 'new')
        self.assertEqual(loaded.data['profiles']['原有接口']['api_key'], 'old-key')
        self.assertEqual(config.read_env(self.root / '.env')['DAYS_BACK'], '9')
        self.assertEqual(loaded.path.stat().st_mode & 0o777, 0o600)

    def test_profile_write_failure_restores_env(self):
        env = self.root / '.env'
        env.write_text('OPENAI_API_KEY=old\nOPENAI_MODEL=before\n')
        original = env.read_bytes()
        real = config.atomic_write
        def fail_profile(path, text, *args):
            if Path(path).name == '.ai_profiles.json':
                raise OSError('disk full')
            return real(path, text, *args)
        with patch.object(config, 'atomic_write', side_effect=fail_profile):
            with self.assertRaises(OSError):
                config.ProfileStore(self.root).activate(self.profile)
        self.assertEqual(env.read_bytes(), original)

    def test_external_env_edit_invalidates_saved_test_state(self):
        store = config.ProfileStore(self.root)
        store.activate(dict(self.profile, tests={'model-a': {'status': '通过'}}))
        config.write_env(self.root / '.env', {'OPENAI_API_KEY': 'changed'})
        self.assertNotIn('tests', store.active())

    def test_lock_excludes_another_process(self):
        with config.operation_lock(self.root):
            result = subprocess.run([sys.executable, '-c',
                'from pathlib import Path; from agent_config import operation_lock; '\
                f'ctx=operation_lock(Path({str(self.root)!r})); ctx.__enter__()'], cwd=REPO, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        with config.operation_lock(self.root):
            pass


class ModelTests(TempCase):
    def test_complete_paginated_list_deduplicated_sorted(self):
        session = Mock()
        session.get.side_effect = [response({'data': [{'id': f'm-{i:03}'} for i in range(120)], 'has_more': True, 'last_id': 'cursor'}),
                                   response({'data': [{'id': 'm-119'}, {'id': 'new-model'}]})]
        models = config.fetch_models(self.profile, session)
        self.assertEqual(len(models), 121)
        self.assertEqual(models[-1], 'new-model')
        self.assertIn('after=cursor', session.get.call_args.args[0])

    def test_link_pagination(self):
        session = Mock()
        session.get.side_effect = [response({'data': [{'id': 'a'}]}, {'next': {'url': '?page=2'}}), response({'data': [{'id': 'b'}]})]
        self.assertEqual(config.fetch_models(self.profile, session), ['a', 'b'])

    def test_cross_origin_pagination_never_forwards_key(self):
        session = Mock()
        session.get.return_value = response({'data': [], 'next': 'https://evil.example/models'})
        with self.assertRaises(ValueError):
            config.fetch_models(self.profile, session)
        self.assertEqual(session.get.call_count, 1)

    def test_pagination_cycle_rejected(self):
        session = Mock()
        session.get.return_value = response({'data': [], 'next': self.profile['base_url'] + '/models'})
        with self.assertRaises(ValueError):
            config.fetch_models(self.profile, session)

    def test_failed_sync_keeps_previous_cache_and_model(self):
        store = config.ProfileStore(self.root)
        with patch.object(config, 'fetch_models', return_value=['a', 'b']):
            store.sync(self.profile)
        before = store.cache(self.profile)
        with patch.object(config, 'fetch_models', side_effect=requests.Timeout):
            with self.assertRaises(requests.Timeout):
                store.sync(self.profile)
        self.assertEqual(store.cache(self.profile), before)
        self.assertEqual(self.profile['model'], 'model-a')

    def test_sync_diff_and_credential_isolation(self):
        store = config.ProfileStore(self.root)
        with patch.object(config, 'fetch_models', side_effect=[['a', 'b'], ['b', 'c']]):
            store.sync(self.profile)
            result = store.sync(self.profile)
        self.assertEqual(result['added'], ['c'])
        self.assertEqual(result['removed'], ['a'])
        self.assertEqual(store.cache(dict(self.profile, api_key='other'))['models'], [])

    def test_bad_number_and_cancel_keep_current_model(self):
        store = config.ProfileStore(self.root)
        with patch.object(config, 'fetch_models', return_value=['a']):
            store.sync(self.profile)
        with patch('builtins.input', side_effect=['999', '0']), patch('sys.stdout', new=io.StringIO()):
            self.assertFalse(console.select_model(store, self.profile, 'model'))
        self.assertEqual(self.profile['model'], 'model-a')

    def test_search_finds_model_beyond_first_page(self):
        store = config.ProfileStore(self.root)
        with patch.object(config, 'fetch_models', return_value=[f'm-{i:03}' for i in range(200)]):
            store.sync(self.profile)
        with patch('builtins.input', side_effect=['s', 'm-199', '1']), patch('sys.stdout', new=io.StringIO()):
            self.assertTrue(console.select_model(store, self.profile, 'model'))
        self.assertEqual(self.profile['model'], 'm-199')

    def test_manual_model_without_list(self):
        store = config.ProfileStore(self.root)
        with patch.object(config, 'fetch_models', side_effect=requests.Timeout), patch('builtins.input', side_effect=['m', 'private-model']), patch('sys.stdout', new=io.StringIO()):
            self.assertTrue(console.select_model(store, self.profile, 'model'))
        self.assertEqual(self.profile['model'], 'private-model')

    def test_failed_test_does_not_save_draft(self):
        store = config.ProfileStore(self.root)
        store.activate(self.profile)
        before = (self.root / '.env').read_bytes()
        with patch.object(console, 'test_profile', return_value=False), patch('sys.stdout', new=io.StringIO()):
            self.assertFalse(console.save_profile(store, dict(self.profile, model='bad')))
        self.assertEqual((self.root / '.env').read_bytes(), before)

    def test_primary_change_does_not_test_broken_fallback(self):
        store = config.ProfileStore(self.root)
        profile = dict(self.profile, fallback='broken-fallback')
        store.activate(profile)
        with patch.object(console, 'test_profile', return_value=True) as probe, patch('builtins.input', return_value='y'):
            self.assertTrue(console.save_profile(store, dict(profile, model='new-primary')))
        self.assertEqual(probe.call_args.kwargs['fields'], ('model',))
        self.assertEqual(store.active()['model'], 'new-primary')
        self.assertEqual(store.active()['fallback'], 'broken-fallback')

    def test_fallback_change_does_not_test_broken_primary(self):
        store = config.ProfileStore(self.root)
        profile = dict(self.profile, model='broken-primary')
        store.activate(profile)
        with patch.object(console, 'test_profile', return_value=True) as probe, patch('builtins.input', return_value='y'):
            self.assertTrue(console.save_profile(store, dict(profile, fallback='new-backup')))
        self.assertEqual(probe.call_args.kwargs['fields'], ('fallback',))
        self.assertEqual(store.active()['model'], 'broken-primary')
        self.assertEqual(store.active()['fallback'], 'new-backup')

    def test_disable_fallback_makes_no_api_test(self):
        store = config.ProfileStore(self.root)
        profile = dict(self.profile, fallback='broken')
        store.activate(profile)
        with patch.object(console, 'test_profile') as probe, patch('builtins.input', return_value='y'):
            self.assertTrue(console.save_profile(store, dict(profile, fallback=''), test_fields=('fallback',)))
        probe.assert_not_called()
        self.assertEqual(store.active()['fallback'], '')

    def test_endpoint_change_revalidates_both_models(self):
        store = config.ProfileStore(self.root)
        profile = dict(self.profile, fallback='backup')
        store.activate(profile)
        with patch.object(console, 'test_profile', return_value=True) as probe, patch('builtins.input', return_value='y'):
            self.assertTrue(console.save_profile(store, dict(profile, base_url='https://new.example/v1')))
        self.assertEqual(probe.call_args.kwargs['fields'], ('model', 'fallback'))

    def test_role_scoped_probe_calls_only_selected_model(self):
        profile = dict(self.profile, fallback='backup')
        with patch('openai.OpenAI'), patch.object(agent, 'analyze_paper', return_value={'分析状态': 'success'}) as analyze, patch('builtins.input', return_value='y'):
            self.assertTrue(console.test_profile(profile, fields=('fallback',)))
        analyze.assert_called_once()
        self.assertEqual(analyze.call_args.args[1], 'backup')
        self.assertEqual(analyze.call_args.kwargs['model_role'], '备用模型')

    def test_failed_fallback_change_preserves_both_models(self):
        store = config.ProfileStore(self.root)
        profile = dict(self.profile, fallback='old-backup')
        store.activate(profile)
        with patch.object(console, 'test_profile', return_value=False) as probe:
            self.assertFalse(console.save_profile(store, dict(profile, fallback='bad-new-backup')))
        self.assertEqual(probe.call_args.kwargs['fields'], ('fallback',))
        self.assertEqual(store.active()['fallback'], 'old-backup')
        self.assertEqual(store.active()['model'], profile['model'])


class AnalysisTests(unittest.TestCase):
    def test_strict_analysis_validation(self):
        self.assertEqual(agent.validate_analysis(json.dumps(analysis()))['相关性分数'], 80)
        for data in ({}, analysis(True), analysis(101), analysis(-1), analysis('80')):
            with self.assertRaises(ValueError):
                agent.validate_analysis(json.dumps(data))
        with self.assertRaises(ValueError):
            agent.validate_analysis('not json')

    def test_fallback_records_model_and_reason(self):
        client = Mock(api_key='secret')
        good = Mock()
        good.choices = [Mock(message=Mock(content=json.dumps(analysis())))]
        client.chat.completions.create.side_effect = [ValueError('missing fields'), good]
        result = agent.analyze_paper(client, 'primary', 'title', 'abstract', retries=1, fallback_model='backup')
        self.assertEqual(result['分析状态'], 'success')
        self.assertEqual(result['分析模型'], 'backup')
        self.assertEqual(result['模型切换原因'], 'missing fields')
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_bad_structure_is_retried_not_cached_as_success(self):
        client = Mock(api_key='secret')
        bad = Mock()
        bad.choices = [Mock(message=Mock(content='{}'))]
        client.chat.completions.create.return_value = bad
        result = agent.analyze_paper(client, 'primary', 'title', 'abstract', retries=2, retry_delay=0)
        self.assertEqual(result['分析状态'], 'failed')
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_http_error_does_not_echo_provider_secret(self):
        error = requests.HTTPError('secret-key echoed')
        error.response = Mock(status_code=401)
        self.assertNotIn('secret-key', config.error_message(error))


class JournalTests(TempCase):
    def test_delete_middle_keeps_final_journal_and_other_settings(self):
        data = {'sources': ['arxiv'], 'target_journals': [{'name': n, 'issn': f'1234-000{i}'} for i, n in enumerate(['first', 'middle', 'last'])], 'db_path': 'custom.db'}
        (self.root / 'config.yaml').write_text(yaml.safe_dump(data))
        with patch.object(console, 'ROOT', self.root), patch('builtins.input', side_effect=['d', '2', 'y', '0']), patch('sys.stdout', new=io.StringIO()):
            console.journals_menu()
        result = yaml.safe_load((self.root / 'config.yaml').read_text())
        self.assertEqual([j['name'] for j in result['target_journals']], ['first', 'last'])
        self.assertEqual(result['db_path'], 'custom.db')

    def test_source_write_produces_valid_yaml_without_literal_newlines(self):
        data = {'sources': ['arxiv'], 'target_journals': [], 'db_path': 'papers.db'}
        with patch.object(console, 'ROOT', self.root):
            console.save_yaml(data)
        self.assertEqual(yaml.safe_load((self.root / 'config.yaml').read_text()), data)


class HTTPIntegrationTests(TempCase):
    def test_real_sdk_and_http_model_list_use_same_analysis_contract(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def send_json(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_GET(self):
                calls.append((self.path, self.headers.get('Authorization')))
                self.send_json({'data': [{'id': 'primary'}, {'id': 'backup'}]})
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((self.path, body['model']))
                self.send_json({'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': body['model'],
                    'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(analysis())}}]})
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            profile = dict(self.profile, base_url=f'http://127.0.0.1:{server.server_port}/custom/v1', model='primary', fallback='backup')
            self.assertEqual(config.fetch_models(profile), ['backup', 'primary'])
            with patch.dict(os.environ, {'NO_PROXY': '127.0.0.1'}, clear=True), patch('builtins.input', return_value='y'), patch('sys.stdout', new=io.StringIO()):
                self.assertTrue(console.test_profile(profile))
            self.assertEqual(calls, [('/custom/v1/models', 'Bearer test-secret'),
                                     ('/custom/v1/chat/completions', 'primary'), ('/custom/v1/chat/completions', 'backup')])
            self.assertEqual(profile['tests']['backup']['status'], '通过')
            self.assertFalse((self.root / 'papers.db').exists())
            self.assertFalse((self.root / 'output').exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class UpdateTests(TempCase):
    def setUp(self):
        super().setUp()
        self.source = self.root / 'source'
        self.install = self.root / 'install'
        self.source.mkdir()
        self.install.mkdir()
        self.launcher = self.root / 'launcher'
        self.launcher.write_text('old launcher')
        self.files = set(update.CONSOLE_FILES) | {'essay_agent.py', 'requirements.txt', 'deploy.sh'}
        for name in self.files:
            shutil.copy2(REPO / name, self.source / name)
            shutil.copy2(REPO / name, self.install / name)
        (self.install / 'esag_console.py').write_text('# OLD CONSOLE\n')
        (self.install / '.code_manifest.json').write_text(json.dumps(sorted(self.files)))
        (self.install / '.installed_version.json').write_text(json.dumps({'program': 'old', 'console': 'old'}))
        (self.install / '.venv').mkdir()
        (self.install / '.venv/bin').mkdir()
        (self.install / '.venv/bin/python').symlink_to(sys.executable)
        self.preserved = {'.env': 'OPENAI_API_KEY=secret\n', 'config.yaml': 'sources: [arxiv]\n',
                          'papers.db': 'database', '.ai_profiles.json': '{}', 'output/report.md': 'report'}
        for name, text in self.preserved.items():
            target = self.install / name
            target.parent.mkdir(exist_ok=True)
            target.write_text(text)
        self.info = {'source': self.source, 'sha': 'new', 'files': sorted(self.files),
                     'hashes': {n: hashlib.sha256((self.source / n).read_bytes()).hexdigest() for n in self.files}}
        # Patch only external system/launcher effects. Real snapshots/copies/rollback run on disk.
        real_path = Path
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(update, 'Path', side_effect=lambda p: self.launcher if str(p) == '/usr/local/bin/esag' else real_path(p)))
        self.stack.enter_context(patch.object(update, 'check_idle'))
        self.stack.enter_context(patch.object(update, 'timer_pause', return_value=False))
        self.stack.enter_context(patch('sys.stdout', new=io.StringIO()))
        self.runner = self.stack.enter_context(patch.object(update, 'run', return_value=Mock(stdout='')))

    def assert_preserved(self):
        for name, value in self.preserved.items():
            self.assertEqual((self.install / name).read_text(), value, name)

    def test_console_update_and_rollback_preserve_data(self):
        self.assertTrue(update.install_update(self.install, self.info, 'console'))
        self.assertEqual(update.versions(self.install), {'program': 'old', 'console': 'new', 'updated_at': update.versions(self.install)['updated_at']})
        self.assert_preserved()
        update.rollback(self.install)
        self.assertEqual((self.install / 'esag_console.py').read_text(), '# OLD CONSOLE\n')
        self.assertEqual(self.launcher.read_text(), 'old launcher')
        self.assert_preserved()

    def test_health_failure_rolls_back_code_and_version(self):
        self.runner.side_effect = lambda args, *a, **k: (_ for _ in ()).throw(RuntimeError('import failed')) if '-c' in args else Mock(stdout='')
        with self.assertRaises(RuntimeError):
            update.install_update(self.install, self.info, 'console')
        self.assertEqual((self.install / 'esag_console.py').read_text(), '# OLD CONSOLE\n')
        self.assertEqual(update.versions(self.install)['console'], 'old')
        self.assert_preserved()

    def test_interrupt_during_update_restores_previous_version(self):
        self.runner.side_effect = lambda args, *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()) if '-c' in args else Mock(stdout='')
        with self.assertRaises(KeyboardInterrupt):
            update.install_update(self.install, self.info, 'console')
        self.assertEqual((self.install / 'esag_console.py').read_text(), '# OLD CONSOLE\n')
        self.assertEqual(update.versions(self.install)['console'], 'old')
        self.assert_preserved()

    def test_active_job_blocks_update_before_any_copy(self):
        with patch.object(update, 'check_idle', side_effect=RuntimeError('busy')):
            with self.assertRaises(RuntimeError):
                update.install_update(self.install, self.info, 'console')
        self.assertEqual((self.install / 'esag_console.py').read_text(), '# OLD CONSOLE\n')
        self.assert_preserved()

    def test_full_update_dependency_failure_leaves_program_and_data(self):
        def runner(args, *a, **k):
            if 'venv' in args:
                Path(args[-1]).mkdir()
            if 'pip' in args:
                raise RuntimeError('dependency failed')
            return Mock(stdout='')
        self.runner.side_effect = runner
        with self.assertRaises(RuntimeError):
            update.install_update(self.install, self.info, 'all')
        self.assertEqual((self.install / 'esag_console.py').read_text(), '# OLD CONSOLE\n')
        self.assertTrue((self.install / '.venv/bin/python').exists())
        self.assert_preserved()

    def test_full_update_and_rollback_restore_dependency_pointer(self):
        def runner(args, *a, **k):
            if 'venv' in args:
                venv = Path(args[-1]); (venv / 'bin').mkdir(parents=True)
                (venv / 'bin/python').symlink_to(sys.executable)
            return Mock(stdout='')
        self.runner.side_effect = runner
        update.install_update(self.install, self.info, 'all')
        new = (self.install / '.venv').resolve()
        self.assertEqual(update.versions(self.install)['program'], 'new')
        update.rollback(self.install)
        self.assertNotEqual((self.install / '.venv').resolve(), new)
        self.assertEqual(update.versions(self.install)['program'], 'old')
        self.assert_preserved()

    def test_modified_download_rejected_before_writes(self):
        (self.source / 'esag').write_text('bad')
        with self.assertRaises(ValueError):
            update.install_update(self.install, self.info)
        self.assertEqual((self.install / 'esag_console.py').read_text(), '# OLD CONSOLE\n')
        self.assert_preserved()

    def test_console_dependency_mismatch_requires_full_update(self):
        (self.install / 'requirements.txt').write_text('different')
        with self.assertRaises(ValueError):
            update.install_update(self.install, self.info, 'console')
        self.assert_preserved()

    def test_latest_version_skips_installation(self):
        (self.install / '.installed_version.json').write_text(json.dumps({'program': 'new', 'console': 'new'}))
        self.assertFalse(update.install_update(self.install, self.info))
        self.runner.assert_not_called()

    def test_runtime_paths_are_never_code(self):
        for name in ('config.yaml', '.env', 'papers.db', 'output/a.md', '../bad', '/absolute', '.venvs/python', 'backups/a'):
            self.assertFalse(update.allowed(name), name)


if __name__ == '__main__':
    unittest.main()
