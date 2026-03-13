import threading


class TermNormalizer:
    def __init__(self):
        self._lock = threading.Lock()

    def normalize(self, element):
        with self._lock:
            name = element.element_name.strip()
            if name.isupper() and len(name) > 4:
                name = name.title()
            element.element_name = name
            return element
