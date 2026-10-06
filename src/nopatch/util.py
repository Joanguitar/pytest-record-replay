

from collections.abc import Mapping, MutableMapping, MutableSequence, MutableSet, Sequence
from datetime import datetime
from typing import Optional

import dill

from nopatch.typing import R


_recording = False
timestamp = datetime.now().isoformat().replace(":", "-")


def recording() -> bool:
    return _recording


def _configure_patch(record: bool):
    """Configure the patching behavior for the current test session."""
    global _recording
    _recording = record


def _for_update(arg: R, rarg: R) -> Optional[R]:
    """Return the post-call argument for updating mutable arguments."""
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
    """Restore any in-place mutations captured after a recorded call."""
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