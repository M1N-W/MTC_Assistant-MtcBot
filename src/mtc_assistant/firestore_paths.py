# -*- coding: utf-8 -*-
"""Firestore path helpers for class-aware data access."""

DEFAULT_CLASS_ID = "mtc12"


def root_collection(db, collection_name: str):
    """Return an existing root collection during the migration window."""
    return db.collection(collection_name)


def class_document(db, class_id: str):
    """Return /classes/{classId}."""
    return db.collection("classes").document(class_id)


def class_collection(db, class_id: str, collection_name: str):
    """Return /classes/{classId}/{collectionName}."""
    return class_document(db, class_id).collection(collection_name)

