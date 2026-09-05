"""Coverage delivery is exercised only against loopback with synthetic credentials."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/report-coverage.sh'
SECRET = 'synthetic-local-test-secret'


class CoverageDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.statuses = [202]
        owner = self

        class Receiver(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append((self.path, dict(self.headers), body))
                self.send_response(owner.statuses.pop(0) if owner.statuses else 202)
                self.end_headers()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def invoke(self, **overrides):
        environment = {**os.environ, 'COVERAGE_SECRET': SECRET, 'REPO': 'fixture/cc-rpi',
                       'TEST_COUNT': '17', 'TEST_FILES': '4', 'TESTS_PASSED': '17', 'TESTS_FAILED': '0',
                       'COVERAGE_PERCENT': '83.25', 'SOURCE_COMMIT_SHA': 'a' * 40,
                       'COVERAGE_RUN_ID': '42', 'COVERAGE_WORKFLOW_REF': 'fixture/cc-rpi/.github/workflows/coverage.yml@refs/heads/main',
                       'SOURCE_TARGET_BRANCH': 'main', 'SOURCE_REPOSITORY': 'fixture/cc-rpi',
                       'COVERAGE_REPORTED_AT': '2026-09-05T12:00:00Z', 'COVERAGE_PROVIDER': 'github-actions',
                       'COVERAGE_ENDPOINT': f'http://127.0.0.1:{self.server.server_port}/synthetic-coverage',
                       'COVERAGE_MAX_ATTEMPTS': '2', 'COVERAGE_RETRY_DELAY_SECONDS': '0', **overrides}
        return subprocess.run(['bash', str(SCRIPT)], env=environment, capture_output=True, text=True, timeout=15)

    def test_payload_is_measured_signed_and_delivered_to_loopback(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.requests), 1)
        path, headers, body = self.requests[0]
        self.assertEqual(path, '/synthetic-coverage')
        expected = 'sha256=' + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(hmac.compare_digest(headers['X-Coverage-Signature-256'], expected))
        payload = json.loads(body)
        self.assertEqual(payload['coveragePercent'], 83.25)
        self.assertEqual(payload['testCount'], 17)
        self.assertEqual(payload['passing'], 17)
        self.assertEqual(payload['source']['commitSha'], 'a' * 40)
        self.assertEqual(payload['source']['targetBranch'], 'main')
        self.assertNotIn(SECRET, result.stdout + result.stderr + body.decode())

    def test_transient_failure_retries_identical_signed_payload(self):
        self.statuses = [503, 202]
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0][2], self.requests[1][2])
        self.assertEqual(self.requests[0][1]['X-Coverage-Signature-256'], self.requests[1][1]['X-Coverage-Signature-256'])

    def test_invalid_measurement_never_reaches_receiver(self):
        result = self.invoke(TEST_COUNT='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_permanent_rejection_is_not_retried(self):
        self.statuses = [403]
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.requests), 1)


if __name__ == '__main__':
    unittest.main()
