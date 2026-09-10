"""API429 image client. Never automatically repeats a POST."""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ORIGIN = 'https://gateway.api429.com'
MAX_RESPONSE = 64 * 1024 * 1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class API429Error(RuntimeError):
    pass

def request(method, path, key, payload=None):
    req = urllib.request.Request(ORIGIN + path, method=method,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
        data=None if payload is None else json.dumps(payload).encode())
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=180) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise API429Error('Response too large; reconcile request before retrying.')
            return response.status, dict(response.headers), json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise API429Error(f'API429 HTTP {exc.code}. No generation retry was sent.') from None
    except (OSError, ValueError):
        raise API429Error('Response unavailable or invalid. Do not create a new run ID until the original request is reconciled.') from None

class Client:
    def __init__(self, key, directory, transport=request, sleep=time.sleep, clock=time.monotonic):
        self.key, self.directory, self.transport = key, Path(directory), transport
        self.sleep, self.clock = sleep, clock
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    def generate(self, payload, run_id, approved, wait_seconds=300):
        if not self.key:
            raise API429Error('Set API429_API_KEY in the ComfyUI server environment.')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id):
            raise API429Error('Run ID must contain 1–80 letters, digits, hyphens or underscores.')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        account = hashlib.sha256(self.key.encode()).hexdigest()[:24]
        record_path = self.directory / f'{account}-{run_id}.json'
        lock_path = record_path.with_suffix('.lock')
        try:
            lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise API429Error('This run is active or was interrupted. Reconcile it before removing its lock.') from None
        os.close(lock)
        try:
            def save(record):
                temp = record_path.with_suffix('.tmp')
                with open(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as f:
                    json.dump(record, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp, record_path)
            if record_path.exists():
                record = json.loads(record_path.read_text())
                if record['digest'] != digest:
                    raise API429Error('Run ID already belongs to different parameters. Use a new ID only for an intentional new generation.')
                if record['state'] == 'complete':
                    return record['response']
                if record['state'] != 'pending':
                    raise API429Error('Previous POST outcome is unknown. Check API429 history/support before starting another run.')
            else:
                if not approved:
                    raise API429Error('Enable allow_paid_generation to submit one paid image request.')
                record = {'digest': digest, 'state': 'submitted'}
                save(record)
                status, headers, data = self.transport('POST', '/v1/images/generations', self.key, payload)
                if status == 200:
                    record.update(state='complete', response=data)
                    save(record)
                    return data
                if status != 202:
                    raise API429Error('Unexpected status. Original request retained; no automatic retry.')
                job = data.get('id') or data.get('job_id')
                path = data.get('result_url') or headers.get('Location')
                if not path and isinstance(job, str) and re.fullmatch(r'[a-zA-Z0-9_-]+', job):
                    path = '/v1/balancer/jobs/' + job + '/result'
                if not isinstance(path, str) or not re.fullmatch(r'/v1/balancer/jobs/[a-zA-Z0-9_-]+/result', path):
                    record.update(response=data)
                    save(record)
                    raise API429Error('Unrecognized async response; original receipt retained for reconciliation.')
                record.update(state='pending', result_path=path)
                save(record)
            end = self.clock() + wait_seconds
            while self.clock() < end:
                status, headers, data = self.transport('GET', record['result_path'], self.key)
                if status == 200:
                    record.update(state='complete', response=data)
                    save(record)
                    return data
                if status != 202:
                    raise API429Error('Unexpected polling status; rerun this same ID to resume without another POST.')
                try:
                    delay = max(1, min(30, int(headers.get('Retry-After', 3))))
                except (TypeError, ValueError):
                    delay = 3
                self.sleep(delay)
            raise API429Error('Still pending. Rerun with the same run ID and parameters to resume polling without another charge request.')
        finally:
            lock_path.unlink(missing_ok=True)
