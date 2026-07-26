r"""Regression test for Vite proxy rewrite.

Bug: 前端请求 `/api/*` 被 Vite proxy 原样转发到后端，
但后端路由没有 `/api` 前缀，导致前端拿到的总是 404。

Fix: vite.config.ts 加 `rewrite: (path) => path.replace(/^\/api/, '')`。

This test directly hits the running Vite dev server (port 5173) and asserts
that /api/* paths now reach the FastAPI backend correctly.
"""
import sys
import httpx

BASE = "http://localhost:5173"
TIMEOUT = 5


def expect(status_or_range, actual, path):
    if isinstance(status_or_range, tuple):
        ok = status_or_range[0] <= actual <= status_or_range[1]
        tag = f"{status_or_range[0]}-{status_or_range[1]}"
    else:
        ok = actual == status_or_range
        tag = str(status_or_range)
    if not ok:
        print(f"FAIL: {path} -> expected {tag}, got {actual}")
        sys.exit(1)
    print(f"  PASS: {path} -> {actual}")


def main():
    print("=== TEST: Vite proxy rewrite (/api → backend) ===\n")

    # GET /api/health should hit backend /health → 200
    r = httpx.get(f"{BASE}/api/health", timeout=TIMEOUT)
    expect(200, r.status_code, "GET /api/health")
    body = r.json()
    assert body.get("status") == "healthy", f"expected healthy, got {body!r}"
    print(f"    body: {body}")

    # GET /api/upload (wrong method) → 405 (proves we hit FastAPI, not SPA fallback)
    r = httpx.get(f"{BASE}/api/upload", timeout=TIMEOUT)
    expect(405, r.status_code, "GET /api/upload")
    body = r.json()
    assert "detail" in body and "Method" in body["detail"], f"expected FastAPI 405 detail, got {body!r}"
    print(f"    body: {body}")

    # GET /api/files/<id> (nonexistent) → 404 with backend detail message
    r = httpx.get(f"{BASE}/api/files/nonexistent-uuid-1234", timeout=TIMEOUT)
    expect(404, r.status_code, "GET /api/files/nonexistent")
    body = r.json()
    assert "detail" in body and "文件不存在" in body["detail"], f"expected backend error, got {body!r}"
    print(f"    body: {body}")

    # POST /api/upload with a real file → 200 (full path tests the file content too)
    import os
    XLSX = r"d:\code\myproject\ProductToolkit\DataReportNew\cn_ecommerce_orders_test.xlsx"
    if os.path.exists(XLSX):
        with open(XLSX, "rb") as f:
            r = httpx.post(
                f"{BASE}/api/upload",
                timeout=TIMEOUT,
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        expect(200, r.status_code, "POST /api/upload (real xlsx)")
        body = r.json()
        assert body.get("rows") == 500, f"expected 500 rows, got {body!r}"
        assert "file_id" in body
        print(f"    rows={body['rows']}, columns={len(body['columns'])}")

    # GET /api/outputs → 200
    r = httpx.get(f"{BASE}/api/outputs", timeout=TIMEOUT)
    expect(200, r.status_code, "GET /api/outputs")
    body = r.json()
    assert "outputs" in body or isinstance(body, list), f"unexpected shape: {body!r}"
    print(f"    body type: {type(body).__name__}")

    print("\n=== ALL PROXY REWRITE TESTS PASSED ===")


if __name__ == "__main__":
    main()