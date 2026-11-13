import math


class BodyIndex:
    def __init__(self, bodies, size=2.0):
        self.size = size
        self.bodies = {}
        self.cells = {}
        self.locations = {}
        self.order = {}
        self.sequence = 0
        for body in bodies:
            self.update(body)

    def update(self, body):
        point = math.floor(body.x / self.size), math.floor(body.y / self.size)
        previous = self.locations.get(body.id)
        self.bodies[body.id] = body
        if previous == point:
            return
        if previous is not None:
            bucket = self.cells[previous]
            bucket.remove(body.id)
            if not bucket:
                del self.cells[previous]
        else:
            self.order[body.id] = self.sequence
            self.sequence += 1
        self.locations[body.id] = point
        self.cells.setdefault(point, set()).add(body.id)

    def remove(self, identifier):
        point = self.locations.pop(identifier, None)
        if point is None:
            return
        bucket = self.cells[point]
        bucket.remove(identifier)
        if not bucket:
            del self.cells[point]
        self.bodies.pop(identifier)
        self.order.pop(identifier)

    def query(self, left, top, right, bottom):
        first_x, first_y = math.floor(left / self.size), math.floor(top / self.size)
        last_x, last_y = math.floor(right / self.size), math.floor(bottom / self.size)
        if (last_x - first_x + 1) * (last_y - first_y + 1) >= len(self.bodies):
            candidates = self.bodies.values()
        else:
            identifiers = set()
            for horizontal in range(first_x, last_x + 1):
                for vertical in range(first_y, last_y + 1):
                    identifiers.update(self.cells.get((horizontal, vertical), ()))
            candidates = (self.bodies[identifier] for identifier in sorted(identifiers, key=self.order.__getitem__))
        for body in candidates:
            if left <= body.x <= right and top <= body.y <= bottom:
                yield body
