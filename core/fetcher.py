import re
import time
import socket
import hashlib
import ipaddress
import urllib.request
import urllib.error
import urllib.parse
from typing import Tuple, Optional, Dict, Any

class URLFetcher:
    """
    Resilient, security-hardened Live URL Fetcher for Landing Page Inspection.
    Features:
    - Browser-grade headers (bypasses basic CDN/bot friction)
    - SSRF protection (blocks private IP ranges & loopback)
    - Redirect tracking & final URL resolution
    - Configurable timeouts & payload size limits (10MB max)
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

            if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                return False, f"Access to localhost/loopback address '{hostname}' is restricted."

            # Check for AWS/GCP metadata service IPs
            if hostname == "169.254.169.254":
                return False, "Access to cloud metadata service IP is blocked."

            # Resolve DNS to check IP range
            ip_str = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip_str)

            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                return False, f"URL resolves to private/internal network IP ({ip_str}), access restricted."

            return True, None
        except Exception as e:
            return False, f"DNS resolution failed for hostname: {e}"

    def fetch_html(self, raw_url: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """
        Fetches HTML from a target URL.
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

        # 2. Build Request with Browser-Like Headers
        headers = {
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1"
        }

        req = urllib.request.Request(url, headers=headers)

        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                final_url = resp.geturl()
                content_type = resp.headers.get("Content-Type", "")

                metadata["status_code"] = status_code
                metadata["final_url"] = final_url
                metadata["content_type"] = content_type
                if final_url != url:
                    metadata["redirect_count"] += 1

                # Read raw bytes with size limit protection
                raw_bytes = resp.read(self.MAX_PAYLOAD_BYTES + 1)
                if len(raw_bytes) > self.MAX_PAYLOAD_BYTES:
                    return None, f"Payload size exceeds maximum allowed limit of {self.MAX_PAYLOAD_BYTES // (1024*1024)}MB.", metadata

                # Determine charset
                charset = "utf-8"
                if "charset=" in content_type.lower():
                    charset = content_type.lower().split("charset=")[-1].split(";")[0].strip()

                try:
                    html_content = raw_bytes.decode(charset, errors="replace")
                except Exception:
                    html_content = raw_bytes.decode("utf-8", errors="replace")

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

        except urllib.error.HTTPError as e:
            metadata["status_code"] = e.code
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            return None, f"HTTP Error {e.code}: {e.reason}", metadata
        except urllib.error.URLError as e:
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            return None, f"Network connection failed: {e.reason}", metadata
        except socket.timeout:
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            return None, f"Request timed out after {self.timeout} seconds.", metadata
        except Exception as e:
            metadata["load_time_ms"] = int((time.time() - start_time) * 1000)
            return None, f"Unexpected fetch error: {str(e)}", metadata
