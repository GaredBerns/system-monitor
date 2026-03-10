"""Temp Mail Engine v2 — Boomlify EDU integration with proper API auth.
Source: https://boomlify.com/RU/EDU-TEMP-MAIL
API: https://v1.boomlify.com (encrypted responses via XOR + x-enc-key-id header)"""

import re, json, time, random, string, threading
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

API_BASE = "https://v1.boomlify.com"

TRANSPORT_KEYRING = {
    "aejru": "Jq4nT6zWe5rM8vPaLs71X", "asdfg": "Sm2nL9qTe5rV8pXaZw61M",
    "bchdk": "Ky3pT5nWv7rQ1mLaZx68A", "bpvhs": "Rd3pK9sTe2yN7mQwVb64Z",
    "cltqg": "Wu5sL2nQe8rT1yPaMx93C", "czmop": "De9fR2sXq5tM1nLbVw84P",
    "fyv": "Hv4kM2nBq8sR1tJcLz93F", "gjbjb": "Lf8pC6sWd3vX1qTuMz40S",
    "guyg": "oP6yT1xHaE9qD4KsLi82M", "gyvg": "Nc5wZ1tQe9yH2rLaKs78D",
    "hgjfh": "rk4kA9fQm8v7W4d2TzX1Y", "hgjfhg": "t2PzKd9sQw1Lm3XyVbN6R",
    "hihji": "bV7nL2cMzR6eJ8QaHp39T", "hklop": "Yd3pM6tQw7nR2sLeVk84N",
    "igug": "Za1sX9qWe3rT7yUiPl56K", "kdjsh": "Zt4mP7nQw3rS6xLeVy82H",
    "kqvtd": "Gk1nP8rTe3yL6mQaZw59J", "nmxas": "Rj6mV4qTe8yN1bLcPw53C",
    "ojigh": "mQ3wN8sRcK5tY2VhUe74Z", "pqlmn": "Ep7mV1qRs6tN4xLbYz82D",
    "prxnl": "Bn7qL4tWe2rP9mXsVd61H", "qwert": "Oy6nR5mTe2pL9qXsWa34J",
    "rtuwq": "Uw2nZ7sQa4tK9pLeMr86B", "svyud": "Hp5mN2qTs8yR1lKaVw73U",
    "tjbqw": "Lm6tQ3nWp9rV2sXeYk45I", "vtycx": "Ha9tQ2mWe5rP8nXsLv61F",
    "vy": "Qs7nF3bLk1pV8xTdRm64G", "wmzlk": "Vb8rP4tQe1mS7nKxZa62O",
    "wzufr": "Nk8rS3pTe1yM6wQvZa75G", "ydnfc": "Cf2mH7vQp6tN9sLxRw83Y",
    "yuiop": "Px1vK8tQe4mN7sLaRw53K", "zqplk": "Tx9vK3dRm5nP2sLaQw71E",
}
MAIN_KEY = "7a9b3c8d2e1f4g5h6i9j0k8l2m4n6o8p"

BASE_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://boomlify.com",
    "Referer": "https://boomlify.com/RU/EDU-TEMP-MAIL",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def _decrypt(encrypted_hex: str, key_id: str = "") -> any:
    key = TRANSPORT_KEYRING.get(key_id, MAIN_KEY) if key_id else MAIN_KEY
    kb = key.encode("utf-8")
    hb = bytes.fromhex(encrypted_hex)
    raw = bytearray(hb[i] ^ kb[i % len(kb)] for i in range(len(hb)))
    return json.loads(raw.decode("utf-8"))


def _api(method: str, path: str, data: dict = None,
         token: str = None, timeout: int = 15) -> any:
    h = dict(BASE_HEADERS)
    if token:
        h["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = json.dumps(data).encode()
    elif method == "POST":
        body = b"{}"
    req = Request(f"{API_BASE}{path}", data=body, headers=h, method=method)
    try:
        resp = urlopen(req, timeout=timeout)
    except HTTPError as e:
        kid = e.headers.get("x-enc-key-id", "") if e.headers else ""
        raw = e.read()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and "encrypted" in parsed:
                return _decrypt(parsed["encrypted"], kid)
            return parsed
        except Exception:
            raise
    kid = resp.headers.get("x-enc-key-id", "")
    raw = resp.read()
    if not raw:
        return None
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and "encrypted" in parsed:
        return _decrypt(parsed["encrypted"], kid)
    return parsed


class BoomlifySession:
    """Manages a guest session with Boomlify API."""

    def __init__(self):
        self.token = None
        self._lock = threading.Lock()

    def ensure_token(self):
        with self._lock:
            if self.token:
                return self.token
            data = _api("POST", "/guest/init")
            self.token = data["token"]
            return self.token

    def refresh_token(self):
        with self._lock:
            self.token = None
        return self.ensure_token()

    def api(self, method, path, data=None):
        tok = self.ensure_token()
        try:
            return _api(method, path, data, token=tok)
        except HTTPError as e:
            if e.code == 401:
                tok = self.refresh_token()
                return _api(method, path, data, token=tok)
            raise


_session = BoomlifySession()


def get_domains(edu_only=True) -> list:
    data = _api("GET", "/domains/public")
    if not data or not isinstance(data, list):
        return []
    if edu_only:
        return [d for d in data if d.get("is_edu") and d.get("is_active")]
    return [d for d in data if d.get("is_active")]


def get_inbox(email: str) -> list:
    """Fetch inbox for email, trying authenticated then public endpoint."""
    for attempt in range(3):
        try:
            data = _session.api("GET", f"/emails/public/{email}")
            if data and isinstance(data, list):
                return data
            if data and isinstance(data, dict) and "messages" in data:
                return data["messages"]
            return [] if data is None else []
        except Exception:
            if attempt < 2:
                time.sleep(1)
                continue
            try:
                data = _api("GET", f"/emails/public/{email}")
                if data and isinstance(data, list):
                    return data
                return []
            except Exception:
                return []


class BoomlifyProvider:
    name = "boomlify"

    def __init__(self):
        self._domains_cache = None
        self._domains_ts = 0

    def _get_domains(self):
        now = time.time()
        if self._domains_cache and now - self._domains_ts < 300:
            return self._domains_cache
        self._domains_cache = get_domains(edu_only=True)
        if not self._domains_cache:
            self._domains_cache = get_domains(edu_only=False)
        self._domains_ts = now
        return self._domains_cache

    def _random_login(self, length=12):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def create_email(self, domain_name=None) -> dict:
        domains = self._get_domains()
        if not domains:
            raise Exception("Boomlify: no domains available")

        if domain_name:
            picked = next((d for d in domains if d["domain"] == domain_name), None)
            if not picked:
                picked = random.choice(domains)
        else:
            picked = random.choice(domains)

        last_err = None
        for attempt in range(3):
            login = self._random_login()
            email_addr = f"{login}@{picked['domain']}"
            try:
                resp = _session.api("POST", "/emails/public/create", {
                    "email": email_addr,
                    "domainId": picked["id"],
                })
                actual_email = email_addr
                if isinstance(resp, dict):
                    if resp.get("error"):
                        last_err = resp["error"]
                        picked = random.choice(domains)
                        time.sleep(1)
                        continue
                    actual_email = resp.get("email", email_addr)

                return {
                    "provider": "boomlify",
                    "email": actual_email,
                    "login": login,
                    "domain": picked["domain"],
                    "domain_id": picked["id"],
                    "is_edu": bool(picked.get("is_edu")),
                    "created_at": datetime.now().isoformat(),
                    "_api_data": resp,
                }
            except Exception as e:
                last_err = str(e)
                _session.refresh_token()
                time.sleep(1)

        raise Exception(f"Boomlify: failed after 3 attempts: {last_err}")

    def check_inbox(self, email_data: dict) -> list:
        email = email_data.get("email", "")
        raw = get_inbox(email)
        results = []
        for m in raw:
            results.append({
                "id": str(m.get("id", m.get("_id", ""))),
                "from": m.get("from", m.get("sender", "")),
                "subject": m.get("subject", ""),
                "date": m.get("date", m.get("received_at", m.get("created_at", ""))),
                "body": m.get("body", m.get("text", "")),
                "html": m.get("html", m.get("body_html", "")),
            })
        return results

    def get_message(self, email_data: dict, msg_id: str) -> dict:
        msgs = self.check_inbox(email_data)
        for m in msgs:
            if str(m["id"]) == str(msg_id):
                return m
        return {}


PROVIDERS = {"boomlify": BoomlifyProvider}


class TempMailManager:
    def __init__(self):
        self.accounts = {}
        self.lock = threading.Lock()
        self._provider = BoomlifyProvider()

    def get_domains(self, edu_only=True) -> list:
        return get_domains(edu_only)

    def create_email(self, provider_name="boomlify", domain_name=None) -> dict:
        email_data = self._provider.create_email(domain_name)
        with self.lock:
            self.accounts[email_data["email"]] = email_data
        return email_data

    def check_inbox(self, email: str) -> list:
        with self.lock:
            email_data = self.accounts.get(email)
        if not email_data:
            email_data = {"email": email, "provider": "boomlify"}
        return self._provider.check_inbox(email_data)

    def get_message(self, email: str, msg_id: str) -> dict:
        with self.lock:
            email_data = self.accounts.get(email)
        if not email_data:
            email_data = {"email": email, "provider": "boomlify"}
        return self._provider.get_message(email_data, msg_id)

    def wait_for_email(self, email: str, timeout=120, poll_interval=1,
                       subject_filter=None) -> dict:
        start = time.time()
        seen_ids = set()
        initial = self.check_inbox(email)
        for m in initial:
            seen_ids.add(m["id"])

        while time.time() - start < timeout:
            time.sleep(poll_interval)
            messages = self.check_inbox(email)
            for m in messages:
                if m["id"] not in seen_ids:
                    if subject_filter and subject_filter.lower() not in m.get("subject", "").lower():
                        seen_ids.add(m["id"])
                        continue
                    return m
        return {}

    def extract_code(self, text: str) -> str:
        patterns = [
            r'(?:code|код|pin|otp|verify|verification)[:\s]*(\d{4,8})',
            r'(\d{6})',
            r'(\d{4,8})',
            r'(?:code|код)[:\s]*([A-Z0-9]{4,10})',
        ]
        for p in patterns:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def extract_link(self, text: str) -> str:
        patterns = [
            r'(https?://[^\s<>"\']+(?:verify|confirm|activate|validate|token|code|register|signup)[^\s<>"\']*)',
            r'(https?://[^\s<>"\']+)',
        ]
        for p in patterns:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def list_accounts(self) -> list:
        with self.lock:
            return list(self.accounts.values())

    def remove_account(self, email: str):
        with self.lock:
            self.accounts.pop(email, None)


mail_manager = TempMailManager()
