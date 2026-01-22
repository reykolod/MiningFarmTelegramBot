import time
import threading
import json
import urllib.parse
import urllib.request
from typing import Optional

try:
    import requests
except Exception:
    requests = None

from config import BITCOIN_EXCHANGE_RATE as FALLBACK_RATE


_cached_rate: float = FALLBACK_RATE
_cached_at: float = 0.0
_CACHE_TTL_SECONDS = 3600         

_USD_DIVISOR: float = 1.0

_lock = threading.Lock()
_refresh_in_progress: bool = False
_refresh_started_at: float = 0.0


def _http_get_json(url: str, params: Optional[dict] = None) -> Optional[object]:
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"

    if requests is not None:
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MiningFarmBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def trigger_bitcoin_rate_refresh(*, force: bool = False) -> None:
    global _cached_rate, _cached_at, _refresh_in_progress, _refresh_started_at

    now = time.time()
    do_sync = False
    with _lock:
        cached_at = _cached_at
        refresh_in_progress = _refresh_in_progress

        if force and cached_at <= 0 and not refresh_in_progress:
            _refresh_in_progress = True
            _refresh_started_at = now
            do_sync = True

    if not force and now - cached_at < _CACHE_TTL_SECONDS:
        return

    if refresh_in_progress and not do_sync:
        return

    if do_sync:
        try:
            price_usd = _fetch_bitcoin_usd_price()
            now_ts = time.time()
            if price_usd and price_usd > 0:
                in_game_rate = float(price_usd) / _USD_DIVISOR
                with _lock:
                    _cached_rate = in_game_rate
                    _cached_at = now_ts
        finally:
            with _lock:
                _refresh_in_progress = False
                _refresh_started_at = 0.0
        return

    with _lock:
        if _refresh_in_progress:
            return
        _refresh_in_progress = True
        _refresh_started_at = now

    def _worker() -> None:
        global _cached_rate, _cached_at, _refresh_in_progress, _refresh_started_at
        try:
            price_usd = _fetch_bitcoin_usd_price()
            now_ts = time.time()
            if price_usd and price_usd > 0:
                in_game_rate = float(price_usd) / _USD_DIVISOR
                with _lock:
                    _cached_rate = in_game_rate
                    _cached_at = now_ts
        finally:
            with _lock:
                _refresh_in_progress = False
                _refresh_started_at = 0.0

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _fetch_bitcoin_usd_price() -> Optional[float]:

    try:
        data = _http_get_json("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        if isinstance(data, dict):
            d = data.get("data")
            if isinstance(d, dict):
                amount = float(d.get("amount") or 0)
                if amount > 0:
                    return amount
    except Exception:
        pass

    try:
        data = _http_get_json("https://api.kraken.com/0/public/Ticker", {"pair": "XBTUSD"})
        if isinstance(data, dict):
            result = data.get("result")
            if isinstance(result, dict):
                for _k, v in result.items():
                    if isinstance(v, dict):
                        c = v.get("c")
                        if isinstance(c, list) and c:
                            amount = float(c[0] or 0)
                            if amount > 0:
                                return amount
    except Exception:
        pass

    try:
        data = _http_get_json("https://api.binance.com/api/v3/ticker/price", {"symbol": "BTCUSDT"})
        if isinstance(data, dict):
            price = float(data.get("price") or 0)
            if price > 0:
                return price
    except Exception:
        pass

    try:
        data = _http_get_json(
            "https://api.coingecko.com/api/v3/simple/price",
            {"ids": "bitcoin", "vs_currencies": "usd"},
        )
        if isinstance(data, dict):
            b = data.get("bitcoin")
            if isinstance(b, dict):
                amount = float(b.get("usd") or 0)
                if amount > 0:
                    return amount
    except Exception:
        pass

    return None


def get_bitcoin_exchange_rate() -> float:

    global _cached_rate, _cached_at, _refresh_in_progress, _refresh_started_at

    now = time.time()
    with _lock:
        cached_rate = _cached_rate
        cached_at = _cached_at
        refresh_in_progress = _refresh_in_progress
        refresh_started_at = _refresh_started_at

                                                                         
    if refresh_in_progress and refresh_started_at and (now - refresh_started_at) > 30:
        with _lock:
            if _refresh_in_progress and _refresh_started_at == refresh_started_at:
                _refresh_in_progress = False
                _refresh_started_at = 0.0
        refresh_in_progress = False

    if now - cached_at < _CACHE_TTL_SECONDS and cached_rate > 0:
        return cached_rate

    if cached_at <= 0 and not refresh_in_progress:
        try:
            price_usd = _fetch_bitcoin_usd_price()
            if price_usd and price_usd > 0:
                in_game_rate = float(price_usd) / _USD_DIVISOR
                with _lock:
                    _cached_rate = in_game_rate
                    _cached_at = now
                return in_game_rate
        except Exception:
            pass

    if not refresh_in_progress:
        trigger_bitcoin_rate_refresh(force=False)

                                                                             
    return cached_rate if cached_rate > 0 else FALLBACK_RATE


def get_bitcoin_last_update() -> Optional[float]:
    with _lock:
        return _cached_at or None

