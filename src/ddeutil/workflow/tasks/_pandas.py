import logging
import math

try:
    import pandas as pd

    logging.debug(f"Polars version: {pd.__version__}")
except ImportError as err:
    raise ImportError(
        "``split_iterable`` function want to use pandas package that does"
        "not install on your interpreter."
    ) from err


def split_iterable(iterable, chunk_size=None, generator_flag: bool = True):
    """
    Split an iterable into mini batch with batch length of batch_number
    supports batch of a pandas dataframe
    usage:
        >> for i in split_iterable([1,2,3,4,5], chunk_size=2):
        >>    print(i)
        [1, 2]
        [3, 4]
        [5]

        for idx, mini_data in split_iterable(batch(df, chunk_size=10)):
            print(idx)
            print(mini_data)
    """

    chunk_size: int = chunk_size or 25000
    num_chunks = math.ceil(len(iterable) / chunk_size)
    if generator_flag:
        for _ in range(num_chunks):
            if isinstance(iterable, pd.DataFrame):
                yield iterable.iloc[_ * chunk_size : (_ + 1) * chunk_size]
            else:
                yield iterable[_ * chunk_size : (_ + 1) * chunk_size]
    else:
        _chunks: list = []
        for _ in range(num_chunks):
            if isinstance(iterable, pd.DataFrame):
                _chunks.append(
                    iterable.iloc[_ * chunk_size : (_ + 1) * chunk_size]
                )
            else:
                _chunks.append(iterable[_ * chunk_size : (_ + 1) * chunk_size])
        return _chunks


def chunks(dataframe: pd.DataFrame, n: int):
    """Yield successive n-sized chunks from dataframe."""
    for i in range(0, len(dataframe), n):
        yield dataframe.iloc[i : i + n]
