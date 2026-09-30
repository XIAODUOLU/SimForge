"""Preserve selection; services remain responsible for render, material and file transactions."""
from contextlib import contextmanager


@contextmanager
def preserve_selection(context):
    """Require Object Mode without forcing a change to the user's editing mode."""
    if context.mode != 'OBJECT':
        raise ValueError("preserve_selection requires Object Mode")
    selected = tuple(context.selected_objects)
    active = context.view_layer.objects.active
    try:
        yield
    finally:
        # Contract: exit in Object Mode and preserve all original input objects.
        for obj in tuple(context.selected_objects):
            obj.select_set(False)
        for obj in selected:
            if context.view_layer.objects.get(obj.name) == obj:
                obj.select_set(True)
        if active is not None and context.view_layer.objects.get(active.name) == active:
            context.view_layer.objects.active = active
        else:
            context.view_layer.objects.active = None
