import os
from urllib.parse import quote


WECHAT_PAYMENT_CONTENT = os.getenv(
    "PAYMENT_WECHAT_DEEP_LINK",
    "wxp://f2f0weex6pzVCbHJS0F58zNgP0qFISXfVQ7wfUjkZm-mVouPfNvF0TLyia4FlY70GzZh",
).strip()
ALIPAY_PAYMENT_CONTENT = os.getenv(
    "PAYMENT_ALIPAY_DEEP_LINK",
    "https://qr.alipay.com/fkx17726pq0vcp2sj5fhgc7",
).strip()
ALIPAY_SCHEME = (
    ALIPAY_PAYMENT_CONTENT
    if ALIPAY_PAYMENT_CONTENT.startswith("alipays://")
    else "alipays://platformapi/startapp?saId=10000007&qrcode="
    + quote(ALIPAY_PAYMENT_CONTENT, safe="")
)


PAYMENT_PAGE_CONFIG = {
    "wechat": {
        "label": "微信支付",
        "deep_link": WECHAT_PAYMENT_CONTENT,
        "qr_url": os.getenv(
            "PAYMENT_WECHAT_QR_URL",
            "https://xingsui.org/pay/wechat.jpg",
        ).strip(),
    },
    "alipay": {
        "label": "支付宝支付",
        "deep_link": ALIPAY_SCHEME,
        "android_intent": (
            "intent://"
            + ALIPAY_SCHEME.removeprefix("alipays://")
            + "#Intent;scheme=alipays;package=com.eg.android.AlipayGphone;end"
        ),
        "universal_link": "https://ulink.alipay.com/?scheme=" + quote(ALIPAY_SCHEME, safe=""),
        "qr_url": os.getenv(
            "PAYMENT_ALIPAY_QR_URL",
            "https://xingsui.org/pay/alipay.jpg",
        ).strip(),
    },
    "support_url": os.getenv(
        "PAYMENT_SUPPORT_URL",
        "https://t.me/+peCBtyuzOzNjNzA1",
    ).strip(),
}
