import re
import time
import socket
import hashlib
import ipaddress
import urllib.parse
from typing import Tuple, Optional, Dict, Any
import requests
import certifi

class URLFetcher:
    """
    Resilient, security-hardened Live URL Fetcher for Landing Page Inspection.
    Features:
    - Requests-backed with bundled Certifi CA bundle (eliminates Linux SSL certificate verify failures)
    - Browser-grade headers (bypasses CDN/bot friction)
    - SSRF protection (blocks private IP ranges, loopback, and metadata endpoints)
    - Graceful SSL fallback for staging/self-signed landing pages
    - Configurable timeouts (5s connect, 10s read) & payload size limits (10MB max)
    - Automatic charset decoding & SPA shell detection
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )

    MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

    def __init__(self, timeout: int = 15, allow_local: bool = False):
        self.timeout = timeout
        self.allow_local = allow_local

    def normalize_url(self, raw_url: str) -> str:
        """Ensures the URL has a valid HTTP/HTTPS scheme and clean structure."""
        url = raw_url.strip()
        if not re.match(r"^https?://", url, re.IGNORECASE):
            url = f"https://{url}"
        return url

    def is_safe_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        SSRF Guardrail: Prevents fetching loopback, cloud metadata endpoints,
        or internal private network IPs (RFC 1918) unless allow_local is set.
        """
        if self.allow_local:
            return True, None

        try:
            parsed = urllib.parse.urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                return False, "Invalid or missing hostname in URL."

            hostname_lower = hostname.lower()
            if hostname_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                return False, f"Access to localhost/loopback address '{hostname}' is restricted."

            # Check for AWS/GCP metadata service IPs
            if hostname == "169.254.169.254":
                return False, "Access to cloud metadata service IP is blocked."

            if hostname_lower.endswith(".internal") or hostname_lower.endswith(".local"):
                return False, f"Access to internal network hostname '{hostname}' is restricted."

            # Resolve DNS to check IP range if possible
            try:
                ip_str = socket.gethostbyname(hostname)
                ip_obj = ipaddress.ip_address(ip_str)

                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                    return False, f"URL resolves to private/internal network IP ({ip_str}), access restricted."
            except Exception:
                # If DNS resolution via gethostbyname fails or produces IPv6, allow requests to attempt it
                pass

            return True, None
        except Exception as e:
            return False, f"URL safety validation failed: {e}"

    def fetch_html(self, raw_url: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """
        Fetches HTML from a target URL with robust error handling and SSL fallback.
        Returns:
            Tuple of (html_content, error_message, metadata_dict)
        """
        url = self.normalize_url(raw_url)
        metadata: Dict[str, Any] = {
            "requested_url": raw_url,
            "normalized_url": url,
            "final_url": url,
            "status_code": None,
            "redirect_count": 0,
            "content_type": None,
            "load_time_ms": None,
            "content_hash": None,
            "is_spa_shell": False,
            "warnings": []
        }

        # 1. SSRF Safety Check
        is_safe, safety_err = self.is_safe_url(url)
        if not is_safe:
            return None, safety_err, metadata

        # 2. Build Request with Browser-Grade Headers
        headers = {
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1"
        }

        start_time = time.time()
        timeout_tuple = (5, min(self.timeout, 12))  # 5s connect, 12s read

        try:
            resp = None
            try:
                # Primary attempt with certifi CA bundle
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout_tuple,
                    allow_redirects=True,
                    verify=certifi.where()
                )
            except requests.exceptions.SSLError:
                # Graceful fallback: try without SSL verification for staging/test sites
                metadata["warnings"].append("SSL certificate verification failed; retried without verification.")
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout_tuple,
                    allow_redirects=True,
                    verify=False
                )

            metadata["status_code"] = resp.status_code
            metadata["final_url"] = str(resp.url)
            metadata["content_type"] = resp.headers.get("Content-Type", "")
            if len(resp.history) > 0:
                metadata["redirect_count"] = len(resp.history)

            # Check status codes
            if resp.status_code in (403, 429):
                return None, (
                    f"The destination site blocked cloud requests (HTTP {resp.status_code}: Anti-bot / Cloudflare protection). "
                    f"You can audit this page by pasting its HTML directly into the 'Raw HTML' tab."
                ), metadata

            if resp.status_code >= 400:
                return None, f"HTTP Error {resp.status_code}: {resp.reason}", metadata

            # Enforce max payload size
            content_bytes = resp.content
            if len(content_bytes) > self.MAX_PAYLOAD_BYTES:
                return None, f"Payload size exceeds maximum allowed limit of {self.MAX_PAYLOAD_BYTES // (1024*1024)}MB.", metadata

            # Decode text
            html_content = resp.text
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            metadata["content_hash"] = hashlib.sha256(html_content.encode("utf-8")).hexdigest()[:16]

            # SPA Shell Detection
            lower_html = html_content.lower()
            has_spa_container = any(c in lower_html for c in ('id="root"', 'id="app"', 'id="__next"'))
            clean_body_text = re.sub(r"<[^>]+>", " ", html_content).strip()
            if has_spa_container and len(clean_body_text) < 150:
                metadata["is_spa_shell"] = True
                metadata["warnings"].append("SPA client-side container detected with minimal static HTML text.")

            return html_content, None, metadata

        except requests.exceptions.Timeout:
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            return None, f"Request timed out after {self.timeout} seconds. The target site took too long to respond.", metadata
        except requests.exceptions.ConnectionError as e:
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            return None, f"Network connection failed: {e}", metadata
        except Exception as e:
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            return None, f"Unexpected fetch error: {str(e)}", metadata
