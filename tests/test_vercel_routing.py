import unittest
from fastapi.testclient import TestClient
from ui.server import app

class TestVercelRouting(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_direct_api_presets(self):
        resp = self.client.get("/api/presets")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_direct_api_audit(self):
        payload = {
            "ad_headline": "Test Headline",
            "ad_description": "Test Description",
            "landing_page_html": "<html><body><h1>Test Headline</h1><p>Test Description</p></body></html>"
        }
        resp = self.client.post("/api/audit", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("match_score", data)

    def test_rewritten_destination_with_query_param(self):
        # Simulates Vercel rewritten destination: /api/index.py?path=/api/presets
        resp = self.client.get("/api/index.py?path=/api/presets")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_rewritten_destination_with_audit_post(self):
        # Simulates Vercel rewritten destination: /api/index.py?path=/api/audit
        payload = {
            "ad_headline": "Test Headline",
            "ad_description": "Test Description",
            "landing_page_html": "<html><body><h1>Test Headline</h1><p>Test Description</p></body></html>"
        }
        resp = self.client.post("/api/index.py?path=/api/audit", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("match_score", data)

    def test_rewritten_destination_with_x_matched_path_header(self):
        # Simulates Vercel header forwarding: x-matched-path
        resp = self.client.get("/api/index.py", headers={"x-matched-path": "/api/presets"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

if __name__ == "__main__":
    unittest.main()
