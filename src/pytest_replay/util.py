"""Internal recording state and mutable-argument replay helpers."""

from collections.abc import (
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Sequence,
)
from datetime import datetime
from typing import Optional

import dill

from pytest_replay.typing import R


_recording = False
timestamp = datetime.now().isoformat().replace(":", "-")


def recording() -> bool:
    """Return whether the current pytest run is recording calls."""
    return _recording


def _configure_patch(record: bool):
    """Set recording mode for wrappers created during this test session."""
    global _recording
    _recording = record


def _for_update(arg: R, rarg: R) -> Optional[R]:
    """Describe how to restore ``arg`` to its post-call value ``rarg``.

    Returns ``None`` when the value is unchanged; for mutable containers,
    returns a copy of the replacement state. Nested immutable containers are
    rebuilt with updates for any mutable values they contain.

    Raises:
        TypeError: If the values have different types or cannot be updated.
        ValueError: If the argument cannot be serialized with dill.
    """
    if type(arg) != type(rarg):
        raise TypeError(
            f"Cannot update mutable argument of type {type(arg).__name__} with {type(rarg).__name__}."
        )
    if not dill.pickles(arg, exact=True):
        raise ValueError(f"Argument {arg} is not picklable.")
    if dill.dumps(arg) == dill.dumps(rarg):
        return None
    if isinstance(arg, (MutableSequence, MutableMapping, MutableSet)):
        return dill.copy(rarg)
    if isinstance(arg, Sequence) and not isinstance(arg, (str, bytes, bytearray)):
        return type(arg)(_for_update(item, ritem) for item, ritem in zip(arg, rarg))  # type: ignore
    if isinstance(arg, Mapping):
        return type(arg)({k: _for_update(v, rarg[k]) for k, v in arg.items()})  # type: ignore
    raise TypeError(f"Cannot update mutable argument of type {type(arg).__name__}.")


def _update_argument(target: R, updated: Optional[R]) -> None:
    """Apply captured post-call state to a replayed argument in place.

    ``None`` indicates that the value was unchanged. Mutable containers are
    updated directly, while immutable containers are traversed to update any
    mutable values nested inside them.

    Raises:
        TypeError: If the saved state has a different type or cannot be applied.
    """
    if updated is None:
        return
    if type(target) != type(updated):
        raise TypeError(
            f"Cannot update mutable argument of type {type(target).__name__} with {type(updated).__name__}."
        )
    if isinstance(target, MutableSequence):
        assert isinstance(updated, MutableSequence)
        target.clear()
        target.extend(updated)
        return
    if isinstance(target, MutableMapping):
        assert isinstance(updated, MutableMapping)
        target.clear()
        target.update(updated)
        return
    if isinstance(target, MutableSet):
        assert isinstance(updated, MutableSet)
        target.clear()
        target |= updated
        return
    if isinstance(target, Sequence) and not isinstance(target, (str, bytes, bytearray)):
        assert isinstance(updated, Sequence)
        for target_item, updated_item in zip(target, updated):
            _update_argument(target_item, updated_item)
        return
    if isinstance(target, Mapping):
        assert isinstance(updated, Mapping)
        for key, value in target.items():
            _update_argument(value, updated[key])
        return
    raise TypeError(f"Cannot update mutable argument of type {type(target).__name__}.")
