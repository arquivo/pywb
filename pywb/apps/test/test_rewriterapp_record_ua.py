from mock import Mock, patch

from pywb.apps.rewriterapp import RewriterApp


BROWSER_UA = 'Mozilla/5.0 (browser)'
RECORD_UA = 'Mozilla/5.0 (compatible; Arquivo-web-crawler/1.0)'


def _make_inputreq():
    inputreq = Mock()
    inputreq.env = {'HTTP_USER_AGENT': BROWSER_UA}
    inputreq.reconstruct_request.return_value = b'GET / HTTP/1.1\r\n\r\n'
    inputreq.warcserver_headers = {}
    return inputreq


def _make_wb_url():
    wb_url = Mock()
    wb_url.url = 'http://example.com/'
    wb_url.is_latest_replay.return_value = True
    wb_url.mod = ''
    return wb_url


class TestRewriterAppRecordUA(object):
    def _make_app(self, recorder_config=None):
        config = {'recorder': recorder_config} if recorder_config else {}
        paths = {'record': 'http://localhost:9999/record/postreq',
                 'replay': 'http://localhost:9999/replay/postreq'}
        return RewriterApp(config=config, paths=paths)

    def test_record_mode_overrides_user_agent(self):
        app = self._make_app({'record_user_agent': RECORD_UA})
        inputreq = _make_inputreq()
        wb_url = _make_wb_url()

        with patch('pywb.apps.rewriterapp.requests.post', return_value=Mock()):
            app._do_req(inputreq, wb_url, {'type': 'record'}, skip_record=False)

        assert inputreq.env['HTTP_USER_AGENT'] == RECORD_UA

    def test_replay_mode_keeps_browser_user_agent(self):
        app = self._make_app({'record_user_agent': RECORD_UA})
        inputreq = _make_inputreq()
        wb_url = _make_wb_url()

        with patch('pywb.apps.rewriterapp.requests.post', return_value=Mock()):
            app._do_req(inputreq, wb_url, {'type': 'replay'}, skip_record=False)

        assert inputreq.env['HTTP_USER_AGENT'] == BROWSER_UA

    def test_no_record_user_agent_configured_keeps_browser_user_agent(self):
        app = self._make_app(None)
        inputreq = _make_inputreq()
        wb_url = _make_wb_url()

        with patch('pywb.apps.rewriterapp.requests.post', return_value=Mock()):
            app._do_req(inputreq, wb_url, {'type': 'record'}, skip_record=False)

        assert inputreq.env['HTTP_USER_AGENT'] == BROWSER_UA

    def test_robots_user_agent_alone_does_not_override_user_agent(self):
        # robots_user_agent only gates persistence (handled in the recorder's
        # RobotsExclusionFilter); it must not affect the outbound UA unless
        # record_user_agent is also set.
        app = self._make_app({'robots_user_agent': 'Arquivo-web-crawler'})
        inputreq = _make_inputreq()
        wb_url = _make_wb_url()

        with patch('pywb.apps.rewriterapp.requests.post', return_value=Mock()):
            app._do_req(inputreq, wb_url, {'type': 'record'}, skip_record=False)

        assert inputreq.env['HTTP_USER_AGENT'] == BROWSER_UA
