"""FastAPI serving contract from HW 8–10, with a controlled streaming simulator."""
import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import re
import socket
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, ProcessCollector, generate_latest
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

MODEL_A_HASH = 'dd3167b4db9e15d2fab00c3a172aee9c248c8963081155f393944faf3f463626'
BUCKETS = (.01, .025, .05, .075, .1, .15, .2, .3, .5, .75, 1, 1.5, 2, 3, 5, 8, 10, 15, 20, 30, 60, 120)
LOG = logging.getLogger('uvicorn.error')


def flag(env_name: str) -> bool:
    raw = os.getenv(env_name, 'false').lower()
    if raw not in {'true', 'false', '1', '0'}:
        raise ValueError(f'{env_name} must be true or false')
    return raw in {'true', '1'}


@dataclass(frozen=True)
class Settings:
    model_path: Path = Path(__file__).with_name('models') / 'A.json'
    model_sha256: str = MODEL_A_HASH
    pod: str = 'local'
    warmup_seconds: float = 2
    early_probes: bool = False
    warmup_fail: bool = False
    process_concurrency: int = 2
    queue_capacity: int = 8
    queue_timeout_seconds: float = 15
    cache_capacity: int = 16
    cache_hit_ms: int = 15
    cache_miss_ms: int = 100
    cpu_work_ms: int = 0
    chunk_delay_ms: int = 30
    enable_experiment_faults: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r'[0-9a-f]{64}', self.model_sha256):
            raise ValueError('MODEL_SHA256 must be a lowercase SHA-256 hex digest')
        if self.process_concurrency < 1 or min(self.queue_capacity, self.cache_capacity) < 0:
            raise ValueError('concurrency must be positive and queue/cache capacities must be nonnegative')
        delays = (self.warmup_seconds, self.queue_timeout_seconds, self.cache_hit_ms,
                  self.cache_miss_ms, self.cpu_work_ms, self.chunk_delay_ms)
        if any(not math.isfinite(delay) or delay < 0 for delay in delays):
            raise ValueError('delays must be finite and nonnegative')
        if not self.queue_timeout_seconds:
            raise ValueError('queue timeout must be positive')

    @classmethod
    def from_env(cls) -> 'Settings':
        probe_mode = os.getenv('PROBE_MODE', 'correct')
        if probe_mode not in ('correct', 'early'):
            raise ValueError('PROBE_MODE must be correct or early')
        return cls(
            model_path=Path(os.getenv('MODEL_PATH', str(cls.model_path))),
            model_sha256=os.getenv('MODEL_SHA256', cls.model_sha256),
            pod=os.getenv('POD_NAME', socket.gethostname()),
            warmup_seconds=float(os.getenv('WARMUP_SECONDS', str(cls.warmup_seconds))),
            early_probes=probe_mode == 'early',
            warmup_fail=flag('WARMUP_FAIL'),
            process_concurrency=int(os.getenv('PROCESS_CONCURRENCY', str(cls.process_concurrency))),
            queue_capacity=int(os.getenv('QUEUE_CAPACITY', str(cls.queue_capacity))),
            queue_timeout_seconds=float(os.getenv('QUEUE_TIMEOUT_SECONDS', str(cls.queue_timeout_seconds))),
            cache_capacity=int(os.getenv('CACHE_CAPACITY', str(cls.cache_capacity))),
            cache_hit_ms=int(os.getenv('CACHE_HIT_MS', str(cls.cache_hit_ms))),
            cache_miss_ms=int(os.getenv('CACHE_MISS_MS', str(cls.cache_miss_ms))),
            cpu_work_ms=int(os.getenv('CPU_WORK_MS', str(cls.cpu_work_ms))),
            chunk_delay_ms=int(os.getenv('CHUNK_DELAY_MS', str(cls.chunk_delay_ms))),
            enable_experiment_faults=flag('ENABLE_EXPERIMENT_FAULTS'),
        )


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant', 'system']
    content: str = Field(max_length=2048)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=1, max_length=16384)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)
    history: list[Message] = Field(default_factory=list, max_length=16)
    prefix: str | None = Field(default=None, min_length=1, max_length=2048)
    parts: StrictInt | None = Field(default=None, ge=1, le=120)
    max_new_tokens: StrictInt | None = Field(default=None, ge=1, le=120)
    chunk_ms: StrictInt | None = Field(default=None, ge=0, le=1000)

    @field_validator('prompt')
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('prompt is blank')
        return value

    @model_validator(mode='after')
    def one_part_limit(self) -> 'GenerateRequest':
        if self.parts is not None and self.max_new_tokens is not None:
            raise ValueError('use parts or max_new_tokens, not both')
        return self

    @property
    def part_count(self) -> int:
        # HW 8–10 clients can still pass max_new_tokens; here it counts simulated parts.
        return self.parts or self.max_new_tokens or 4


@dataclass(frozen=True)
class ModelArtifact:
    version: str
    response_prefix: str

    @classmethod
    def load(cls, path: Path, expected_sha256: str) -> 'ModelArtifact':
        with path.open('rb') as file:
            contents = file.read(64 * 1024 + 1)
        if len(contents) > 64 * 1024:
            raise ValueError('simulator artifact is larger than 64 KiB')
        actual_sha256 = hashlib.sha256(contents).hexdigest()
        if not hmac.compare_digest(actual_sha256, expected_sha256):
            raise ValueError('simulator artifact SHA-256 mismatch')
        artifact = json.loads(contents)
        if artifact['backend_mode'] != 'simulated':
            raise ValueError('expected a simulator artifact')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', artifact['version']):
            raise ValueError('invalid artifact version')
        prefix = artifact['response_prefix']
        if not isinstance(prefix, str) or not 0 < len(prefix) <= 256:
            raise ValueError('invalid artifact response_prefix')
        return cls(artifact['version'], prefix)


class Simulator:
    def __init__(self, settings: Settings, artifact: ModelArtifact) -> None:
        self.settings = settings
        self.artifact = artifact
        self.warmed = False
        self.draining = False
        self.slots = asyncio.Semaphore(settings.process_concurrency)
        self.waiting = 0
        self.running = 0
        self.cache: OrderedDict[bytes, None] = OrderedDict()
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        self.ttfc = Histogram('hw11_ttfc_seconds', 'Time to first chunk for successful requests',
                              buckets=BUCKETS, registry=self.registry)
        self.duration = Histogram('hw11_request_duration_seconds', 'Server duration of successful requests',
                                  buckets=BUCKETS, registry=self.registry)
        self.requests = Counter('hw11_requests_total', 'Generate outcomes', ('outcome',), registry=self.registry)
        for outcome in ('completed', 'rejected', 'aborted'):
            self.requests.labels(outcome)
        self.cache_events = Counter('hw11_cache_total', 'Simulated prefix lookups', ('result',), registry=self.registry)
        for result in ('hit', 'miss'):
            self.cache_events.labels(result)
        for name, description, read in (
            ('running', 'Requests with a processing slot', lambda: self.running),
            ('waiting', 'Requests in the application queue', lambda: self.waiting),
            ('warmed', 'Backend warmup completed successfully', lambda: int(self.warmed)),
            ('ready', 'Current result of the readiness check', lambda: int(self.ready)),
        ):
            metric = Gauge(f'hw11_{name}', description, registry=self.registry)
            metric.set_function(read)

    @property
    def startup(self) -> bool:
        return self.settings.early_probes or self.warmed

    @property
    def ready(self) -> bool:
        return self.startup and not self.draining

    def log(self, event: str, **fields: object) -> None:
        LOG.info(json.dumps({'event': event, 'ts_unix_ms': round(time.time() * 1_000),
                             'pod': self.settings.pod, 'version': self.artifact.version,
                             'backend_mode': 'simulated', **fields}, ensure_ascii=False))

    async def warmup(self) -> None:
        self.log('warmup_started', seconds=self.settings.warmup_seconds, probe_mode='early' if self.settings.early_probes else 'correct')
        await asyncio.sleep(self.settings.warmup_seconds)
        if self.settings.warmup_fail:
            self.log('warmup_failed')
        else:
            self.warmed = True
            self.log('warmup_finished', ready=self.ready)

    async def acquire(self) -> str | None:
        if not self.ready:
            return 'draining' if self.draining else 'warming'
        if self.slots.locked():
            if self.waiting >= self.settings.queue_capacity:
                return 'queue_full'
            self.waiting += 1
            try:
                async with asyncio.timeout(self.settings.queue_timeout_seconds):
                    await self.slots.acquire()
            except TimeoutError:
                return 'queue_timeout'
            finally:
                self.waiting -= 1
            # This request entered while Ready. Drain lets already admitted work finish.
        else:
            await self.slots.acquire()
        self.running += 1
        return None

    def release(self) -> None:
        self.running -= 1
        self.slots.release()

    def lookup(self, key: str) -> bool:
        digest = hashlib.sha256(key.encode()).digest()
        hit = digest in self.cache
        if hit:
            self.cache.move_to_end(digest)
        elif self.settings.cache_capacity:
            self.cache[digest] = None
            if len(self.cache) > self.settings.cache_capacity:
                self.cache.popitem(last=False)
        self.cache_events.labels('hit' if hit else 'miss').inc()
        return hit

    def publish_outcome(self, outcome: str, details: dict, **fields: object) -> None:
        self.requests.labels(outcome).inc()
        self.log(f'request_{outcome}', **details, **fields)


async def spend_cpu(milliseconds: int) -> None:
    """Spend approximately the configured CPU time and yield regularly to probes."""
    remaining = milliseconds * 1_000_000
    if not remaining:
        return
    payload = b'mlops-simulated-prefill' * 512
    while remaining > 0:
        began = time.thread_time_ns()
        until = began + min(remaining, 3_000_000)
        now = began
        while now < until:
            hashlib.sha256(payload).digest()
            now = time.thread_time_ns()
        remaining -= now - began
        await asyncio.sleep(0)


def ndjson(event: dict) -> bytes:
    return (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


def trace_headers(server: Simulator, request_id: str, request: Request, **extra: str) -> dict:
    return {'X-Request-ID': request_id, 'X-Pod-Name': server.settings.pod,
            'X-Model-ID': server.artifact.version, 'X-Backend-Mode': 'simulated',
            'X-Client-IP': client_ip(request), 'X-Artifact-SHA256': server.settings.model_sha256, **extra}


def trace_id(request: Request) -> str:
    identifier = request.headers.get('X-Request-ID', '')
    return identifier if re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}', identifier) else uuid.uuid4().hex


def local_admin(request: Request) -> None:
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'Loopback only')


class ManagedStream(StreamingResponse):
    def __init__(self, events: AsyncIterator[bytes], headers: dict[str, str], on_close: Callable[[], None]):
        super().__init__(events, media_type='application/x-ndjson', headers=headers)
        self.on_close = on_close

    async def __call__(self, scope, receive, send):
        # The response owns the processing slot until the ASGI send ends or the client disconnects.
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.on_close()


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings.from_env()
        artifact = ModelArtifact.load(config.model_path, config.model_sha256)
        server = Simulator(config, artifact)
        app.state.server = server
        server.log('artifact_loaded', model_sha256=config.model_sha256)
        task = asyncio.create_task(server.warmup())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            server.log('shutdown', running=server.running, waiting=server.waiting)

    service = FastAPI(lifespan=lifespan)

    @service.get('/health')
    async def health(request: Request):
        server = request.app.state.server
        return {'alive': True, 'pod': server.settings.pod, 'version': server.artifact.version,
                'backend_mode': 'simulated', 'artifact_sha256': server.settings.model_sha256}

    @service.get('/startup')
    async def startup(request: Request):
        server = request.app.state.server
        return JSONResponse({'startup': server.startup, 'warmed': server.warmed}, 200 if server.startup else 503)

    @service.get('/ready')
    async def readiness(request: Request):
        server = request.app.state.server
        return JSONResponse({'ready': server.ready, 'warmed': server.warmed, 'draining': server.draining,
                             'version': server.artifact.version, 'artifact_sha256': server.settings.model_sha256},
                            200 if server.ready else 503)

    @service.get('/metrics')
    async def metrics(request: Request):
        return Response(generate_latest(request.app.state.server.registry), media_type=CONTENT_TYPE_LATEST)

    @service.post('/drain')
    async def drain(request: Request):
        local_admin(request)
        server = request.app.state.server
        server.draining = True
        server.log('drain_started', running=server.running, waiting=server.waiting)
        return {'draining': True, 'running': server.running, 'waiting': server.waiting}

    @service.post('/fault/kill')
    async def kill(request: Request):
        server = request.app.state.server
        if not server.settings.enable_experiment_faults:
            raise HTTPException(404)
        local_admin(request)
        server.log('abrupt_exit', running=server.running, waiting=server.waiting)
        os._exit(137)

    @service.exception_handler(RequestValidationError)
    async def bad_request(request: Request, error: RequestValidationError):
        server = request.app.state.server
        request_id = trace_id(request)
        if request.url.path == '/generate' and request.method == 'POST':
            server.publish_outcome('rejected', {'request_id': request_id, 'session_id': None,
                                                'client_ip': client_ip(request)}, reason='validation', status=422)
        return JSONResponse({'detail': [{k: entry[k] for k in ('type', 'loc', 'msg')} for entry in error.errors()],
                             'request_id': request_id, 'pod': server.settings.pod,
                             'version': server.artifact.version, 'backend_mode': 'simulated'},
                            status_code=422, headers=trace_headers(server, request_id, request))

    @service.post('/generate')
    async def generate(body: GenerateRequest, request: Request):
        server: Simulator = request.app.state.server
        started = time.monotonic()
        request_id = trace_id(request)
        tags = {'request_id': request_id, 'session_id': body.session_id, 'client_ip': client_ip(request)}
        metadata = {'request_id': request_id, 'pod': server.settings.pod,
                    'version': server.artifact.version, 'model_id': server.artifact.version,
                    'backend_mode': 'simulated', 'artifact_sha256': server.settings.model_sha256}
        missing = await server.acquire()
        if missing:
            status = 429 if missing in ('queue_full', 'queue_timeout') else 503
            server.publish_outcome('rejected', tags, reason=missing, status=status)
            return JSONResponse({**metadata, 'detail': missing}, status, headers=trace_headers(server, request_id, request))

        woke = server.warmed
        waited = time.monotonic() - started
        hit = server.lookup(body.prefix if body.prefix is not None else body.prompt[:128])
        prefill_ms = server.settings.cache_hit_ms if hit else server.settings.cache_miss_ms
        chunk_ms = body.chunk_ms if body.chunk_ms is not None else server.settings.chunk_delay_ms
        admission = {'warmed': woke, 'queue_ms': round(waited * 1_000, 3), 'cache_hit': hit}
        server.log('request_admitted', **tags, **admission)
        answer = (f'{server.artifact.response_prefix}: ' +
                  '\n'.join([*(f'{turn.role}: {turn.content}' for turn in body.history), body.prompt]))
        opened = 0
        first = None
        outcome = 'aborted'

        async def stream():
            nonlocal opened, first, outcome
            await asyncio.sleep(prefill_ms / 1_000)
            await spend_cpu(server.settings.cpu_work_ms)
            for step in range(body.part_count):
                if step and chunk_ms:
                    await asyncio.sleep(chunk_ms / 1_000)
                offset = step * len(answer) // body.part_count
                end = (step + 1) * len(answer) // body.part_count
                part = answer[offset:end] or ' '
                if first is None:
                    first = time.monotonic()
                opened += 1
                yield ndjson({**metadata, **admission, 'event': 'chunk', 'part': step + 1, 'text': part})
            yield ndjson({**metadata, **admission, 'event': 'done', 'parts': opened, 'done': True})
            outcome = 'completed'

        def finish_stream() -> None:
            server.release()
            elapsed = time.monotonic() - started
            ttfc = first - started if first is not None else None
            if outcome == 'completed' and ttfc is not None:
                server.ttfc.observe(ttfc)
                server.duration.observe(elapsed)
            server.publish_outcome(outcome, tags, **admission, parts=opened,
                                   ttfc_ms=round(ttfc * 1_000, 3) if ttfc is not None else None,
                                   elapsed_ms=round(elapsed * 1_000, 3))

        headers = trace_headers(server, request_id, request, **{
            'X-Warmed': str(woke).lower(), 'X-Cache-Hit': str(hit).lower(),
            'X-Queue-MS': str(admission['queue_ms']), 'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no',
        })
        return ManagedStream(stream(), headers, finish_stream)

    return service


app = create_app()
