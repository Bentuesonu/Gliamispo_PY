class Eighths:
    __slots__ = ("whole", "eighths")

    def __init__(self, whole=0, eighths=0):
        self.whole = whole + eighths // 8
        self.eighths = eighths % 8

    @classmethod
    def from_decimal(cls, value):
        w = int(value)
        remainder = value - w
        e = min(7, round(remainder * 8))
        return cls(w, e)

    @classmethod
    def from_string(cls, s):
        s = s.strip()
        parts = s.split()
        if len(parts) == 2 and "/" in parts[1]:
            w = int(parts[0])
            num, den = parts[1].split("/")
            e = int(num) * 8 // int(den)
            return cls(w, min(7, e))
        if "/" in s:
            num, den = s.split("/")
            return cls(0, int(num) * 8 // int(den))
        return cls(int(s), 0)

    @property
    def total_eighths(self):
        return self.whole * 8 + self.eighths

    def __sub__(self, other):
        diff = self.total_eighths - other.total_eighths
        return Eighths(diff // 8, diff % 8)

    def __eq__(self, other):
        return self.total_eighths == other.total_eighths

    def __repr__(self):
        if self.eighths == 0:
            return str(self.whole)
        return f"{self.whole} {self.eighths}/8"


def scene_duration(page_start, page_end):
    start = Eighths.from_decimal(page_start)
    end = Eighths.from_decimal(page_end)
    return end - start
