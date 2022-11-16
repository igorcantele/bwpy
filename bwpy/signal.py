import re
import abc
import functools
import numpy as np
import numpy.lib.stride_tricks as np_tricks


__all__ = []


def _transformer_factory(cls):
    @functools.wraps(cls)
    def transformer_factory(slice, *args, **kwargs):
        return slice._transform(cls(*args, **kwargs))

    return transformer_factory


class Transformer(abc.ABC):
    def __init_subclass__(cls, operator=None, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        name = operator or re.sub("([a-z0-9])([A-Z])", r"\1_\2", cls.__name__).lower()
        globals()[name] = _transformer_factory(cls)
        __all__.append(name)

    def _apply_window(self, data, bin_size):
        rows = data.shape[0]
        cols = data.shape[1]
        window_shape = (rows, cols, bin_size)
        # sliding window returns more complex shape like (num_windows, 1, 1, rows, cols, bin_size)
        # with the reshape we get rid of the unnecessary complexity (1, 1)
        return np_tricks.sliding_window_view(data, window_shape).reshape(
            -1, rows, cols, bin_size
        )

    @abc.abstractmethod
    def __call__(self, data, file):
        pass


class Variation(Transformer):
    def __init__(self, bin_size):
        self.bin_size = bin_size

    def __call__(self, data, slice, file):
        print("calling ", self.__class__.__name__)
        if data.ndim < 3:
            return data
        else:
            windows = self._apply_window(data, self.bin_size)
            return np.max(np.abs(windows), axis=3) - np.min(np.abs(windows), axis=3)


class Amplitude(Transformer):
    def __init__(self, bin_size):
        self.bin_size = bin_size

    def __call__(self, data, slice, file):
        print("calling ", self.__class__.__name__)
        if data.ndim < 3:
            return data
        else:
            windows = self._apply_window(data, self.bin_size)
            return np.max(np.abs(windows), axis=3)


class Energy(Transformer):
    def __init__(self, bin_size):
        self.bin_size = bin_size

    def __call__(self, data, slice, file):
        print("calling ", self.__class__.__name__)
        if data.ndim < 3:
            return data
        else:
            windows = self._apply_window(data, self.bin_size)
            return np.sum(np.square(windows), axis=3)


class Raw(Transformer):
    def __call__(self, data, slice, file):
        print("calling ", self.__class__.__name__)
        return np.moveaxis(data, 2, 0)


class DetectArtifacts(Transformer):
    def __call__(self, data, slice, file):
        print("calling ", self.__class__.__name__)
        if data.ndim < 3:
            return data
        else:
            up_limit = file.convert(file.max_volt) * 0.98
            out_bounds = data > up_limit
            mask = np.sum(out_bounds, axis=(1, 2)) > 80
            return mask


class Shutter(Transformer):
    def __init__(self, data, delay_ms):
        self.delay_ms = delay_ms
        self.data = data

    def __call__(self, mask, slice, file):
        print("calling ", self.__class__.__name__)
        if mask.ndim > 1:
            raise ValueError("mask must be a 1dim array.")

        delay = self.ms_to_idx(file, self.delay_ms)
        for i in range(len(mask) - 1, 0, -1):
            if mask[i]:
                mask[i : i + delay] = 1

        return self.data[mask]

    def ms_to_idx(self, file, delay_ms):
        return int(delay_ms * file.sampling_rate * 1000)
