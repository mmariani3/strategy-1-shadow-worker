"""Bounded public HTTPS GETs: exact host allowlist, pinned public IP, no credentials."""
import http.client
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser


class FetchBlocked(ValueError):
    pass


def public_url(url):
    if not isinstance(url, str) or len(url) > 4096 or re.search(r'[\s\\\x00-\x1f\x7f]', url):
        raise FetchBlocked('INVALID_URL')
    p = urlsplit(url)
    if (p.scheme != 'https' or not p.hostname or p.username is not None or p.password is not None
            or p.port not in (None, 443) or not p.hostname.isascii() or p.hostname.endswith('.')):
        raise FetchBlocked('PUBLIC_HTTPS_REQUIRED')
    host = p.hostname.lower()
    if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', host) or '.' not in host:
        raise FetchBlocked('PUBLIC_HOST_REQUIRED')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise FetchBlocked('IP_LITERAL_NOT_ALLOWED')
    if re.search(r'%(?:0[0-9a-f]|1[0-9a-f]|7f)', url, re.I):
        raise FetchBlocked('ENCODED_CONTROL_CHARACTER')
    return urlunsplit(('https', host, p.path or '/', p.query, ''))


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Connect to the already-validated numeric address, keeping TLS hostname verification.
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


class PublicFetcher:
    def __init__(self, allowed_hosts, user_agent, max_bytes=4_000_000):
        if not isinstance(user_agent, str) or not re.fullmatch(r'[^\r\n]{5,200}', user_agent) or '@' not in user_agent:
            raise FetchBlocked('IDENTIFIED_USER_AGENT_REQUIRED')
        self.allowed_hosts = {urlsplit(public_url('https://' + h + '/')).hostname for h in allowed_hosts}
        if not self.allowed_hosts or type(max_bytes) is not int or not 1 <= max_bytes <= 10_000_000:
            raise FetchBlocked('BOUNDED_FETCH_CONFIGURATION_REQUIRED')
        self.user_agent, self.max_bytes = user_agent, max_bytes
        self.robots = {}
        self.last_request = 0
        self.http_requests = 0

    def _get(self, url, validators=None, limit=None):
        url = public_url(url)
        p = urlsplit(url)
        if p.hostname not in self.allowed_hosts:
            raise FetchBlocked('HOST_NOT_ALLOWED')
        addresses = {info[4][0] for info in socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise FetchBlocked('NONPUBLIC_DNS_RESULT')
        # One request/second per process, including robots. Hosted aggregate limiting is separate.
        time.sleep(max(0, self.last_request + 1 - time.monotonic()))
        self.last_request = time.monotonic()
        headers = {'User-Agent': self.user_agent, 'Accept': 'text/html,text/plain,application/xhtml+xml',
                   'Accept-Encoding': 'identity', 'Connection': 'close'}
        for key, value in (validators or {}).items():
            if key not in ('If-None-Match', 'If-Modified-Since') or not isinstance(value, str) or re.search(r'[\r\n]', value):
                raise FetchBlocked('INVALID_CONDITIONAL_HEADER')
            headers[key] = value
        connection = PinnedHTTPS(p.hostname, sorted(addresses)[0], 15)
        try:
            self.http_requests += 1
            connection.request('GET', urlunsplit(('', '', p.path, p.query, '')), headers=headers)
            response = connection.getresponse()
            metadata = {k.lower(): v for k, v in response.getheaders()
                        if k.lower() in ('content-type','content-length','content-encoding','etag','last-modified','location','retry-after')}
            if response.status != 200:
                return {'status': response.status, 'headers': metadata, 'body': b''}
            if metadata.get('content-encoding', 'identity').lower() not in ('identity', ''):
                raise FetchBlocked('COMPRESSED_RESPONSE_NOT_SUPPORTED')
            maximum = min(limit or self.max_bytes, self.max_bytes)
            if int(metadata.get('content-length', '0')) > maximum:
                raise FetchBlocked('DOCUMENT_TOO_LARGE')
            chunks, count, deadline = [], 0, time.monotonic() + 30
            while True:
                if time.monotonic() > deadline:
                    raise FetchBlocked('DOCUMENT_TIME_LIMIT')
                chunk = response.read(min(65536, maximum + 1 - count))
                if not chunk:
                    break
                count += len(chunk)
                if count > maximum:
                    raise FetchBlocked('DOCUMENT_TOO_LARGE')
                chunks.append(chunk)
            return {'status': response.status, 'headers': metadata, 'body': b''.join(chunks)}
        finally:
            connection.close()

    def fetch(self, url, validators=None):
        url = public_url(url)
        host = urlsplit(url).hostname
        if host not in self.allowed_hosts:
            raise FetchBlocked('HOST_NOT_ALLOWED')
        if host not in self.robots:
            result = self._get('https://' + host + '/robots.txt', limit=256000)
            if result['status'] == 404:
                lines = ['User-agent: *', 'Disallow:']
            elif result['status'] == 200:
                lines = result['body'].decode('utf-8-sig', errors='strict').splitlines()
                if any('<html' in line.lower() for line in lines):
                    raise FetchBlocked('ROBOTS_NOT_READABLE')
            else:
                raise FetchBlocked('ROBOTS_UNAVAILABLE')
            policy = RobotFileParser()
            policy.parse(lines)
            self.robots[host] = policy
        policy = self.robots[host]
        if not policy.can_fetch(self.user_agent, url):
            raise FetchBlocked('ROBOTS_DISALLOWED')
        delay = policy.crawl_delay(self.user_agent)
        rate = policy.request_rate(self.user_agent)
        if (delay and delay > 1) or (rate and rate.seconds / rate.requests > 1):
            raise FetchBlocked('SLOWER_SITE_SCHEDULE_REQUIRED')
        # Redirects are recorded, not followed. No cookies, login, proxy credentials or JS execution.
        return self._get(url, validators)
