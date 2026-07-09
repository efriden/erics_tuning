from queue import Queue, Empty, Full
from typing import TypeVar, Generic, Callable

import numpy as np
from numpy.typing import NDArray

from logging import getLogger

logger = getLogger(__name__)

DType = TypeVar("DType", bound=np.generic)


class DataBuffer(Generic[DType]):
    """A wrapper of a queue object that acts as a FIFO array of ndarrays.

    Parent classes can type this as lists or queues:
    Example:
        data_buffer: DataBuffer[np.float32] = DataBuffer()
    This typing will be enforced by typecheckers - but ignored at runtime.
    Is this the best way? probably not. but i like it and fuck you! :P

    Args:
        maxsize - the amount of elements to hold in the buffer at once.
                (defaults to 10)
        comparer: Callable - optional comparing function that compares two elements
            and returns True if the former should be ranked 'higher' than the latter.
            if supplied, the owner can call get_current_top() to get the 'top' item
            currently in the buffer and get_all_time_top() to get the 'top' from the lifetime
            of the buffer.
            Calling clear_all_time_top() sets the total_top to the currently 'top' item
            in the buffer.

    """

    current_top: NDArray[DType] | None
    all_time_top: NDArray[DType] | None
    queue: Queue[NDArray[DType]]
    comparer: Callable[[NDArray[DType], NDArray[DType]], bool] | None

    def __init__(
        self,
        maxsize: int = 10,
        comparer: Callable[[NDArray[DType], NDArray[DType]], bool] | None = None,
    ) -> None:
        self.queue: Queue[NDArray[DType]] = Queue(maxsize=maxsize)
        self.comparer: Callable[[NDArray[DType], NDArray[DType]], bool] | None = (
            comparer
        )
        self.current_top = None
        self.all_time_top = None

    def pop(self) -> NDArray[DType] | None:
        """Pops the oldest element in the buffer out.

        If the buffer was instantiated with a comparer, the current top item is updated.
        (this should be reimplemented, the current version works but is a bit hacky,
        in ways detailed in comments below)

        Returns:
            NDArray[DType] | None: the oldest element in the buffer.

        """
        try:
            popped: NDArray[DType] = self.queue.get_nowait()
            if self.comparer is not None:
                new_top: NDArray[DType] | None = None
                # this iteration is slightly bad - the queue.queue is the internal dequeue
                # object that is not 'meant' to be accessed. But the alternative is maintaining
                # a separate mirrored dequeue for inspection and i dont want to do that. sue me.
                #
                # also: we do the whole O(n), go through all elements, thing with every pop,
                # which is not very demure. Fix it yourself if you want to be like that.
                for data_point in self.queue.queue:
                    if new_top is None:
                        new_top = data_point
                        continue
                    if self.comparer(data_point, new_top):
                        new_top = data_point
                if new_top is None:
                    raise RuntimeError(
                        "Something went wrong with finding a new top item"
                    )
                self.current_top = new_top
            return popped

        except Empty:
            return None

    def push(self, new_point: NDArray[DType]) -> None:
        try:
            self.queue.put(new_point)
        except Full:
            self.pop()
            self.queue.put(new_point)
        finally:
            if self.comparer is not None:
                self.check_new_top(new_point)

    def check_new_top(self, candidate: NDArray[DType]) -> None:
        if self.comparer is None:
            raise RuntimeError("Comparer called when no comparer function defined.")
        if self.current_top is None and self.all_time_top is None:
            self.current_top: NDArray[DType] = candidate
            self.all_time_top: NDArray[DType] = candidate
            return
        if self.current_top is None or self.all_time_top is None:
            logger.warning("Mismatch between current and all time top assignment.")
            return
        if self.comparer(candidate, self.current_top):
            self.current_top: NDArray[DType] = candidate
            if self.comparer(self.current_top, self.all_time_top):
                self.all_time_top: NDArray[DType] = candidate

    def get_current_top(self) -> NDArray[DType]:
        if self.current_top is None:
            raise RuntimeError("get_current_top called on empty buffer")
        return self.current_top

    def get_all_time_top(self) -> NDArray[DType]:
        if self.all_time_top is None:
            raise RuntimeError("get_current_top called on empty buffer")
        return self.all_time_top

    def clear_all_time_top(self) -> None:
        self.all_time_top = self.current_top

    def get_copy(self) -> list[NDArray[DType]]:
        # as mentioned above, this is not proper - but it works.
        return [x.copy() for x in self.queue.queue]

    def as_ndarray(self) -> NDArray[DType]:
        return np.stack(arrays=self.get_copy())
