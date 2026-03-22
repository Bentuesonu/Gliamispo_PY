import threading


class MLScheduler:
    def __init__(self, feedback_loop, interval_seconds=3600):
        self._feedback = feedback_loop
        self._interval = interval_seconds
        self._timer = None
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._schedule_next()

    def stop(self):
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _schedule_next(self):
        self._timer = threading.Timer(self._interval, self._run_cycle)
        self._timer.daemon = True
        self._timer.start()

    def _run_cycle(self):
        with self._lock:
            if not self._running:
                return
        self._feedback._check_retrain()
        with self._lock:
            if self._running:
                self._schedule_next()

    def trigger_now(self):
        self._feedback._check_retrain()
