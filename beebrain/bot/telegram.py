"""
a very small telegram bot api client. stdlib only.

the token never leaves this process except in the api url, over https.
"""
import json
import urllib.error
import urllib.request

API = "https://api.telegram.org/bot%s/%s"


class TelegramError(Exception):
    def __init__(self, message, code=None, retry_after=None):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after

    @property
    def fatal(self):
        return self.code in (401, 404, 409)


class Telegram:
    def __init__(self, token, post=None):
        if not token or ":" not in token:
            raise ValueError("that does not look like a bot token from @BotFather")
        self.token = token
        self.post = post or self._post

    def _post(self, method, payload, timeout=40):
        req = urllib.request.Request(API % (self.token, method), data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                d = json.load(e)
            except ValueError:
                raise TelegramError("%s: http %d" % (method, e.code), code=e.code) from None
        except (OSError, ValueError) as e:
            raise TelegramError("%s: %s" % (method, type(e).__name__)) from None
        if not d.get("ok"):
            raise TelegramError("%s: %s" % (method, str(d.get("description", "failed")).replace(self.token, "[redacted]")),
                                code=d.get("error_code"), retry_after=d.get("parameters", {}).get("retry_after"))
        return d.get("result")

    def call(self, method, **payload):
        return self.post(method, {k: v for k, v in payload.items() if v is not None})

    def updates(self, offset, timeout=20):
        return self.post("getUpdates", {"offset": offset, "timeout": timeout,
                                        "allowed_updates": ["message", "callback_query"]}) or []

    def send(self, chat_id, text, buttons=None, preview=False):
        markup = {"inline_keyboard": buttons} if buttons else None
        return self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                         reply_markup=markup, link_preview_options={"is_disabled": not preview})

    def answer(self, callback_id, text=None):
        return self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)
