"""
read only market data from public apis. no keys, nothing is ever sent but a GET.

  dexscreener    discovery from the latest token profiles and boosts, and batch prices,
                 up to 30 pairs a call. generous limits.
  geckoterminal  the newest pools on a network. tight limits, so it is polled slowly
                 and backs off on 429.

the browser twin in web/trade/bee.js calls the same endpoints.
"""
import json
import time
import urllib.error
import urllib.request

from .features import norm_dexscreener, norm_gecko

DS = "https://api.dexscreener.com"
GT = "https://api.geckoterminal.com/api/v2"
GT_NETWORK = {"solana": "solana", "base": "base", "bsc": "bsc"}
CHAINS = ("solana", "base", "bsc", "robinhood")

DS_DISCOVER_S = 30.0
GT_DISCOVER_S = 90.0
REFRESH_S = 15.0
BATCH = 30
UA = "beebrain-field/0.3 (+https://github.com/h100envy/beebrain)"


class RateLimited(Exception):
    pass


def get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(url)
        raise


class Feed:
    """pull based: call due(now) to see what to fetch, or just poll(now)"""

    def __init__(self, chain, fetch=get_json, gecko=True):
        if chain not in CHAINS:
            raise ValueError("chain must be one of " + ", ".join(CHAINS))
        self.chain = chain
        self.fetch = fetch
        self.gecko = gecko and chain in GT_NETWORK
        self.next = {"ds": 0.0, "gt": 0.0, "px": 0.0}
        self.gt_wait = GT_DISCOVER_S
        self.errors = 0
        self.calls = 0
        self.status = "starting"

    def _get(self, url):
        self.calls += 1
        return self.fetch(url)

    def discover_ds(self):
        tokens = []
        for path in ("/token-profiles/latest/v1", "/token-boosts/latest/v1"):
            for t in self._get(DS + path) or []:
                if t.get("chainId") == self.chain and t.get("tokenAddress") not in tokens:
                    tokens.append(t.get("tokenAddress"))
        return self.pairs_for_tokens(tokens)

    def pairs_for_tokens(self, tokens):
        best = {}
        for i in range(0, len(tokens), BATCH):
            for p in self._get("%s/tokens/v1/%s/%s" % (DS, self.chain, ",".join(tokens[i:i + BATCH]))) or []:
                s = norm_dexscreener(p)
                cur = best.get(s["token"])
                if cur is None or s["liq"] > cur["liq"]:
                    best[s["token"]] = s
        return list(best.values())

    def discover_gt(self):
        d = self._get("%s/networks/%s/new_pools?page=1&include=base_token" % (GT, GT_NETWORK[self.chain]))
        toks = {t["id"]: t.get("attributes", {}) for t in d.get("included", [])}
        return [norm_gecko(p, self.chain, toks) for p in d.get("data", [])]

    def refresh(self, pairs):
        out = []
        for i in range(0, len(pairs), BATCH):
            d = self._get("%s/latest/dex/pairs/%s/%s" % (DS, self.chain, ",".join(pairs[i:i + BATCH])))
            out += [norm_dexscreener(p) for p in (d or {}).get("pairs") or []]
        return out

    def poll(self, now_s, tracked):
        """returns (new snapshots, refreshed snapshots). never raises on network trouble."""
        new, fresh = [], []
        try:
            if now_s >= self.next["ds"]:
                self.next["ds"] = now_s + DS_DISCOVER_S
                new += self.discover_ds()
            if self.gecko and now_s >= self.next["gt"]:
                try:
                    new += self.discover_gt()
                    self.gt_wait = GT_DISCOVER_S
                except RateLimited:
                    self.gt_wait = min(600.0, self.gt_wait * 2)
                self.next["gt"] = now_s + self.gt_wait
            if tracked and now_s >= self.next["px"]:
                self.next["px"] = now_s + REFRESH_S
                fresh += self.refresh(tracked)
            self.status = "live"
        except (urllib.error.URLError, OSError, ValueError, RateLimited) as e:
            self.errors += 1
            self.status = "feed error: %s" % (getattr(e, "reason", None) or e.__class__.__name__)
        return new, fresh


def now_ms():
    return time.time() * 1000.0
