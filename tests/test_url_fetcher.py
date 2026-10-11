import unittest
from unittest.mock import patch, MagicMock
from core.fetcher import URLFetcher
from core.audit_engine import AuditEngine
from core.schemas import AuditState

class TestURLFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = URLFetcher(timeout=5)
        self.engine = AuditEngine(allow_local_fetch=False)

    def test_url_normalization(self):
        """URLFetcher must ensure scheme is present."""
        self.assertEqual(self.fetcher.normalize_url("example.com/pricing"), "https://example.com/pricing")
        self.assertEqual(self.fetcher.normalize_url("http://example.com"), "http://example.com")
        self.assertEqual(self.fetcher.normalize_url("https://example.com/test"), "https://example.com/test")

    def test_ssrf_protection_loopback_and_metadata(self):
        """SSRF: Restrict access to localhost, loopback, and metadata endpoints."""
        is_safe, err = self.fetcher.is_safe_url("http://localhost:8000")
        self.assertFalse(is_safe)
        self.assertIn("restricted", err.lower())

        is_safe, err = self.fetcher.is_safe_url("http://127.0.0.1/admin")
        self.assertFalse(is_safe)
        self.assertIn("restricted", err.lower())

        is_safe, err = self.fetcher.is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(is_safe)
        self.assertIn("blocked", err.lower())

    @patch("urllib.request.urlopen")
    def test_fetch_html_success(self, mock_urlopen):
        """Mock successful response from external landing page."""
        sample_html = (
            "<!DOCTYPE html><html><head><title>Test</title></head>"
            "<body><h1>Rates from 4.9% APR</h1><p>Fast application process.</p></body></html>"
        )
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = "https://kestrelfunding.com/loans"
        mock_resp.headers.get.return_value = "text/html; charset=utf-8"
        mock_resp.read.return_value = sample_html.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        mock_urlopen.return_value = mock_resp

        # Bypass DNS resolution check for mocked domain
        with patch.object(self.fetcher, "is_safe_url", return_value=(True, None)):
            html, err, meta = self.fetcher.fetch_html("https://kestrelfunding.com/loans")

            self.assertIsNone(err)
            self.assertIsNotNone(html)
            self.assertIn("Rates from 4.9% APR", html)
            self.assertEqual(meta["status_code"], 200)
            self.assertEqual(meta["final_url"], "https://kestrelfunding.com/loans")
            self.assertIsNotNone(meta["content_hash"])

    @patch("urllib.request.urlopen")
    def test_audit_url_integration(self, mock_urlopen):
        """AuditEngine.audit_url executes full 7-phase audit from live URL."""
        sample_html = (
            "<!DOCTYPE html><html><body>"
            "<h1>Apply in 10 Minutes</h1>"
            "<p>Rates from 6.9% APR for qualified applicants.</p>"
            "</body></html>"
        )
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = "https://example.com"
        mock_resp.headers.get.return_value = "text/html"
        mock_resp.read.return_value = sample_html.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.object(self.engine.fetcher, "is_safe_url", return_value=(True, None)):
            result = self.engine.audit_url(
                ad_headline="Apply in 10 Minutes | Rates from 6.9% APR",
                ad_description="Fast online funding.",
                landing_page_url="https://example.com"
            )

            self.assertEqual(result.audit_state, AuditState.COMPLETED)
            self.assertGreater(result.match_score, 0)
            self.assertEqual(result.audit_metadata["source_url"], "https://example.com")
            self.assertEqual(len(result.findings), 2)

    def test_audit_url_ssrf_blocked(self):
        """AuditEngine.audit_url gracefully handles blocked SSRF URLs."""
        result = self.engine.audit_url(
            ad_headline="Fast loans",
            ad_description="Great service",
            landing_page_url="http://127.0.0.1/internal"
        )
        self.assertEqual(result.audit_state, AuditState.FAILED_UNREADABLE_INPUT)
        self.assertIn("restricted", result.scoring_unavailability_reason.lower())

if __name__ == "__main__":
    unittest.main()
