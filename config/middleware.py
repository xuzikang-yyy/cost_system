"""预览环境适配：跨站 WebView 中 Cookie 需要 SameSite=None; Secure。"""


class PreviewCookieMiddleware:
    """当请求来自 HTTPS 预览代理或 WebView 时，调整响应 Cookie 属性。

    本地直接访问 http://localhost:8000 时不做改动，仍然使用 Lax，
    避免非 HTTPS 环境下 Secure Cookie 无法写入。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        is_preview = (
            request.is_secure()
            or "webview_request_time" in request.get_full_path()
            or request.META.get("HTTP_X_FORWARDED_PROTO", "").lower() == "https"
        )
        if is_preview:
            for cookie in response.cookies.values():
                cookie["samesite"] = "None"
                cookie["secure"] = True
        return response
