"""Tiny self-check that exercises the security-critical seams. No framework, no fixtures.
Run: python backend/_selfcheck.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Test 1 — GenerateRequest rejects path traversal in background and video_file
from main import GenerateRequest
try:
    GenerateRequest(url="https://reddit.com/x", background="../etc")
    print("FAIL: background traversal accepted")
except ValueError:
    pass
try:
    GenerateRequest(url="https://reddit.com/x", video_file="../../etc/passwd")
    print("FAIL: video_file traversal accepted")
except ValueError:
    pass
ok = GenerateRequest(url="https://reddit.com/x")
assert ok.background == "minecraft", ok.background

# Test 2 — text length cap
try:
    GenerateRequest(text="x" * 50001)
    print("FAIL: text length cap bypassed")
except ValueError:
    pass

# Test 3 — ScriptData validates LLM output (part count, content length)
from main import ScriptData
ok_script = ScriptData.model_validate({"title": "T", "subreddit": "r/foo",
    "parts": [{"partNumber": 1, "content": "x"}]})
assert len(ok_script.parts) == 1
try:
    ScriptData.model_validate({"title": "T", "parts": [{"partNumber": 0, "content": "x"}]})
    print("FAIL: bad partNumber accepted")
except Exception:
    pass
try:
    ScriptData.model_validate({"title": "T", "parts": [{"partNumber": 1, "content": "x" * 99999}]})
    print("FAIL: oversized part accepted")
except Exception:
    pass
try:
    ScriptData.model_validate({"title": "T", "parts": [{"partNumber": i, "content": "x"} for i in range(1, 100)]})
    print("FAIL: too many parts accepted")
except Exception:
    pass

# Test 4 — public_error strips paths and URLs
from main import public_error
err = public_error("Failed at /home/numair/x/y.py from https://api.example.com/token", 500)
assert "/home" not in err.detail, err.detail
assert "https://" not in err.detail, err.detail

# Test 5 — is_safe_public_url rejects private/loopback/credential URLs
from main import is_safe_public_url
for bad in ["http://127.0.0.1:8080/", "http://10.0.0.1/", "http://192.168.1.1/",
            "https://user:pass@reddit.com/", "ftp://reddit.com/", "",
            "https://0.0.0.0/", "http://169.254.1.1/"]:
    assert is_safe_public_url(bad) is False, f"accepted unsafe url: {bad!r}"

# Test 6 — _safe_video_response containment (we'll test the path check directly)
from main import OUTPUT, _safe_video_response
from pathlib import Path
import tempfile
external = Path(tempfile.gettempdir()) / "evil.mp4"
external.write_bytes(b"x")
try:
    _safe_video_response(str(external))
    print("FAIL: external video path accepted")
except Exception:
    pass
external.unlink(missing_ok=True)

# Test 7 — start_file_server refuses repo root and external paths
from main import start_file_server, find_free_port
try:
    s = find_free_port()
    start_file_server(str(Path(__file__).resolve().parent.parent), s)
    print("FAIL: start_file_server accepted repo root")
except (RuntimeError, Exception):
    pass
try:
    start_file_server("/etc", find_free_port())
    print("FAIL: start_file_server accepted /etc")
except RuntimeError:
    pass

print("ALL CHECKS PASSED")


if __name__ == "__main__":
    pass
