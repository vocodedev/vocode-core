import pytest

from vocode.streaming.utils import generate_from_async_iter_with_lookahead, generate_with_is_last


@pytest.mark.asyncio
async def test_generate_with_is_last():
    async def async_gen():
        yield 1
        yield 2
        yield 3

    async_iter = generate_with_is_last(async_gen()).__aiter__()

    assert await async_iter.__anext__() == (1, False)
    assert await async_iter.__anext__() == (2, False)
    assert await async_iter.__anext__() == (3, True)


@pytest.mark.asyncio
async def test_generate_with_lookahead_long():
    async def async_gen():
        yield 1
        yield 2
        yield 3
        yield 4
        yield 5

    async_iter = generate_from_async_iter_with_lookahead(async_gen(), 2).__aiter__()

    expected_gen = [
        [1, 2, 3],
        [2, 3, 4],
        [3, 4, 5],
    ]
    idx = 0
    async for buffer in async_iter:
        assert buffer == expected_gen[idx]
        idx += 1


@pytest.mark.asyncio
async def test_generate_with_lookahead_short():
    async def async_gen():
        yield 1
        yield 2

    async_iter = generate_from_async_iter_with_lookahead(async_gen(), 2).__aiter__()

    expected_gen = [[1, 2]]
    idx = 0
    async for buffer in async_iter:
        assert buffer == expected_gen[idx]
        idx += 1
