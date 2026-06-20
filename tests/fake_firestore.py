class FakeDocSnapshot:
    def __init__(self, exists, data=None):
        self.exists = exists
        self._data = dict(data or {})

    def to_dict(self):
        return dict(self._data)


class FakeDocRef:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def get(self, transaction=None):
        if self.path in self.db.store:
            return FakeDocSnapshot(True, self.db.store[self.path])
        return FakeDocSnapshot(False)

    def set(self, data, merge=False):
        if merge:
            current = dict(self.db.store.get(self.path, {}))
            current.update(data)
            self.db.store[self.path] = current
            return
        self.db.store[self.path] = dict(data)

    def update(self, data):
        current = dict(self.db.store.get(self.path, {}))
        current.update(data)
        self.db.store[self.path] = current

    def delete(self):
        self.db.store.pop(self.path, None)

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, doc_id):
        return FakeDocRef(self.db, f"{self.path}/{doc_id}")

    def stream(self):
        prefix = f"{self.path}/"
        for path, data in sorted(self.db.store.items()):
            if path.startswith(prefix) and "/" not in path[len(prefix):]:
                yield FakeDocSnapshot(True, data)


class FakeTransaction:
    def get(self, ref):
        return ref.get(transaction=self)

    def set(self, ref, data, merge=False):
        ref.set(data, merge=merge)

    def update(self, ref, data):
        ref.update(data)

    def delete(self, ref):
        ref.delete()


class FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self, name)

    def transaction(self):
        return FakeTransaction()


def seed_registry(db, class_id, grade_level, *, status="active", active_term_id=None, room_label=None):
    data = {
        "display_name": class_id.upper(),
        "status": status,
        "grade_level": grade_level,
    }
    if active_term_id:
        data["active_term_id"] = active_term_id
    if room_label:
        data["room_label"] = room_label
    db.store[f"system/class_registry/{class_id}/main"] = data


def seed_class_user(db, class_id, user_id, *, status="active", verification_status="unverified"):
    db.store[f"classes/{class_id}/users/{user_id}"] = {
        "user_id": user_id,
        "role": "student",
        "status": status,
        "verification_status": verification_status,
    }
