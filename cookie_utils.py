# cookie_utils.py
from http.cookiejar import CookieJar, Cookie
from typing import List, Tuple, Optional
import time

def parse_netscape_cookies_txt(raw: str) -> List[dict]:
    """
    Return a list of rows with keys:
    domain, include_subdomains, path, secure, expires, name, value
    """
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):  # skip comments/blank
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            continue
        domain, include_sub, path, secure, expires, name, value = parts
        rows.append({
            "domain": domain,
            "include_subdomains": include_sub.upper() == "TRUE",
            "path": path or "/",
            "secure": secure.upper() == "TRUE",
            "expires": int(expires) if expires.isdigit() else 0,
            "name": name,
            "value": value,
        })
    return rows

def to_requests_cookiejar(rows: List[dict]) -> CookieJar:
    jar = CookieJar()
    now = int(time.time())
    for r in rows:
        # Play nice with bad expiries
        exp = r["expires"] if r["expires"] > 0 else now + 86400 * 30
        c = Cookie(
            version=0,
            name=r["name"],
            value=r["value"],
            port=None,
            port_specified=False,
            domain=r["domain"].lstrip("."),  # strip leading dot for requests
            domain_specified=True,
            domain_initial_dot=r["domain"].startswith("."),
            path=r["path"] or "/",
            path_specified=True,
            secure=r["secure"],
            expires=exp,
            discard=False,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": None},
            rfc2109=False,
        )
        jar.set_cookie(c)
    return jar

def to_playwright_cookies(rows: List[dict]) -> list:
    """
    Convert to a list acceptable to context.add_cookies().
    """
    out = []
    for r in rows:
        domain = r["domain"].lstrip(".")  # Playwright accepts plain domain
        cookie = {
            "name": r["name"],
            "value": r["value"],
            "domain": domain,
            "path": r["path"] or "/",
            "secure": r["secure"],
            "httpOnly": False,   # unknown in Netscape format
            "sameSite": "Lax",   # best-effort default
        }
        if r["expires"] and r["expires"] > 0:
            cookie["expires"] = r["expires"]
        out.append(cookie)
    return out

def parse_netscape_for_both(raw: str) -> Tuple[CookieJar, list]:
    rows = parse_netscape_cookies_txt(raw)
    return to_requests_cookiejar(rows), to_playwright_cookies(rows)
