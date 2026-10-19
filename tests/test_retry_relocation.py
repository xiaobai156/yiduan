import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from duan_app.domain import Candidate, Site, SiteResult
from duan_app.fetcher import RenderedPage, render_browser_document
from duan_app.documents import collect_documents
from duan_app.retry_failed import merge_success, retry


class FakePage:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def goto(self, url, **kwargs):
        self.calls.append(url)
        self.url = self.routes[url]

    def wait_for_load_state(self, *args, **kwargs):
        pass

    def wait_for_function(self, *args, **kwargs):
        pass

    def content(self):
        return '<p>292期绝杀一段【2段】</p>'


class RelocationTests(unittest.TestCase):
    def test_observed_homepage_restores_same_topic(self):
        old = 'https://old.test/topic/123.html'
        new = 'https://new.test/topic/123.html'
        page = FakePage({old: 'https://new.test/#dq', new: new})
        result = render_browser_document(page, old, 10, TimeoutError)
        self.assertEqual(result.source_url, new)
        self.assertEqual(page.calls, [old, new])

    def test_wrong_topic_rejected(self):
        old = 'https://old.test/topic/123.html'
        with self.assertRaisesRegex(ValueError, '身份不一致'):
            render_browser_document(FakePage({old: 'https://new.test/topic/456.html'}), old, 10, TimeoutError)

    def test_loaded_document_survives_resource_timeout(self):
        old = 'https://old.test/topic/123.html'
        page = FakePage({old: old})
        def timeout(*args, **kwargs):
            raise TimeoutError()
        page.wait_for_load_state = timeout
        self.assertEqual(render_browser_document(page, old, 10, TimeoutError).source_url, old)

    def test_unchanged_homepage_does_not_guess_a_host(self):
        old = 'https://old.test/topic/123.html'
        with self.assertRaisesRegex(ValueError, '身份不一致'):
            render_browser_document(FakePage({old: 'https://old.test/'}), old, 10, TimeoutError)

    def test_loop_rejected(self):
        old = 'https://old.test/topic/123.html'
        new = 'https://new.test/topic/123.html'
        with self.assertRaisesRegex(ValueError, '循环'):
            render_browser_document(FakePage({old: 'https://new.test/', new: 'https://new.test/'}), old, 10, TimeoutError)

    def test_browser_metadata_and_relative_script_source(self):
        fetched = []
        def fetch(url, *args):
            fetched.append(url)
            return 'independent script'
        documents, _ = collect_documents(
            'https://old.test/topic/123.html', 10, True,
            issue_filter={292}, site_name='作者', pick='top',
            fetch_page_text_fn=lambda *a: '<html>shell</html>',
            render_page_text_fn=lambda *a: RenderedPage('<script src="/upload/script/data.js"></script>', 'https://new.test/topic/123.html'),
            fetch_text_fn=fetch,
        )
        self.assertIn('https://new.test/upload/script/data.js', fetched)
        self.assertTrue(any(m.get('source_url') == 'https://new.test/topic/123.html' for m in documents.document_metadata))


class RetryTests(unittest.TestCase):
    def test_only_recovered_cache_record_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fail, success, cache = [root / n for n in ('292期-段-失败.txt', '292期-段.txt', 'cache.json')]
            site = Site('恢复站', 'https://old.test/topic/123.html', 'top')
            line = f'失败 {site.name} {site.url} 方向: top 期数: 292 阶段: 校验 原因: 无期数\n'
            fail.write_text(line, encoding='utf-8')
            success.write_text('3段 原有站\n\n内容 次数 排名\n3段 1 1\n', encoding='utf-8')
            untouched = dict(name='其他站', url='https://other.test', pick='bottom', fingerprint={'291': '7段'}, status='error', error='保留', notes=['不要改'])
            target = dict(name=site.name, url=site.url, pick=site.pick, fingerprint={'291': '1段'}, status='error', error='无期数', notes=['无候选数据', '其他审核原因'])
            payload = dict(periods=10, sites=[target, untouched], _meta=dict(format='duan_recent_10_cache.v2', max_search=30, source_sites=str(root/'sites.json'), source_sites_hash='', summary=dict(site_count=2)))
            (root/'sites.json').write_text(json.dumps([{'name': r['name'], 'url': r['url'], 'pick': r['pick']} for r in (target, untouched)]), encoding='utf-8')
            import hashlib
            payload['_meta']['source_sites_hash'] = hashlib.sha256((root/'sites.json').read_bytes()).hexdigest()
            cache.write_text(json.dumps(payload), encoding='utf-8')
            candidate = Candidate(292, '292期', '2段', '', '', 100, 0, 0)
            def processor(*args):
                self.assertEqual(args[4], {292})
                return SiteResult(1, site, [candidate], None, 'OK')
            self.assertEqual(retry(fail, success, [site], cache_path=cache, sites_path=root/'sites.json', processor=processor), (1, 0))
            result = json.loads(cache.read_text(encoding='utf-8-sig'))
            self.assertEqual(result['sites'][1], untouched)
            self.assertEqual(result['sites'][0]['fingerprint'], {'291': '1段', '292': '2段'})
            self.assertIn('其他审核原因', result['sites'][0]['notes'])
            self.assertNotIn('无候选数据', result['sites'][0]['notes'])
            self.assertNotIn('失败 恢复站', fail.read_text(encoding='utf-8-sig'))
            text = success.read_text(encoding='utf-8-sig')
            self.assertLess(text.index('3段 原有站'), text.index('2段 恢复站'))
            self.assertLess(text.index('2段 恢复站'), text.index('内容'))

    def test_missing_cache_never_crawls_or_deletes_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fail = root/'292期-段-失败.txt'
            original = '失败 作者 https://example.test/topic/1.html 方向: top 期数: 292 阶段: 校验 原因: 无期数\n'
            fail.write_text(original, encoding='utf-8')
            with patch('duan_app.retry_failed.process_site') as processor:
                with self.assertRaises(FileNotFoundError):
                    retry(fail, root/'292期-段.txt', [], cache_path=root/'missing.json')
                processor.assert_not_called()
            self.assertEqual(fail.read_text(encoding='utf-8'), original)

    def test_failed_retry_preserves_all_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fail, success = root/'292期-段-失败.txt', root/'292期-段.txt'
            site = Site('作者', 'https://example.test/topic/1.html', 'bottom')
            original = f'失败 作者 {site.url} 方向: bottom 期数: 292 阶段: 校验 原因: 无期数\r\n'
            fail.write_bytes(original.encode('utf-8-sig'))
            success.write_bytes('1段 原有站\r\n'.encode('utf-8-sig'))
            before = [p.read_bytes() for p in (fail, success)]
            result = SiteResult(1, site, [], original, 'FAIL')
            self.assertEqual(retry(fail, success, [site], processor=lambda *a: result), (0, 1))
            self.assertEqual([p.read_bytes() for p in (fail, success)], before)

    def test_conflicting_success_is_preserved(self):
        text = '1段 原站\r\n内容 次数 排名\r\n1段 1 1\r\n'
        merged, accepted = merge_success(text, {'原站': '2段'})
        self.assertEqual(merged, text)
        self.assertEqual(accepted, {})


if __name__ == '__main__':
    unittest.main()
