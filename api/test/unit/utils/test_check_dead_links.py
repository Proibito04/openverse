import asyncio

import pook
import pytest
from aiohttp.client import ClientSession

from api.utils.check_dead_links import HEADERS, check_dead_links


@pook.on
def test_sends_user_agent():
    query_hash = "test_sends_user_agent"
    results = [{"provider": "best_provider_ever"} for _ in range(40)]
    image_urls = [f"https://example.org/{i}" for i in range(len(results))]
    start_slice = 0

    head_mock = (
        pook.head(pook.regex(r"https://example.org/\d"))
        .headers(HEADERS)
        .times(len(results))
        .reply(200)
        .mock
    )

    check_dead_links(query_hash, start_slice, results, image_urls)

    assert head_mock.calls == len(results)
    requested_urls = [req.rawurl for req in head_mock.matches]
    for url in image_urls:
        assert url in requested_urls


def test_handles_timeout(monkeypatch):
    """
    Test that case where timeout occurs.

    Note: This test takes just over 3 seconds to run as it simulates network delay of
    3 seconds.
    """
    query_hash = "test_handles_timeout"
    results = [{"identifier": i, "provider": "best_provider_ever"} for i in range(1)]
    image_urls = [f"https://example.org/{i}" for i in range(len(results))]
    start_slice = 0

    async def raise_timeout_error(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(ClientSession, "_request", raise_timeout_error)
    check_dead_links(query_hash, start_slice, results, image_urls)

    # `check_dead_links` directly modifies the results list
    # if the results are timing out then they're considered dead and discarded
    # so should not appear in the final list of results.
    assert len(results) == 0


@pytest.mark.parametrize("provider", ("thingiverse", "flickr"))
def test_403_considered_dead(provider):
    query_hash = f"test_{provider}_403_considered_dead"
    other_provider = "fake_other_provider"
    results = [
        {"identifier": i, "provider": provider if i % 2 else other_provider}
        for i in range(4)
    ]
    image_urls = [f"https://example.org/{i}" for i in range(len(results))]
    start_slice = 0

    head_mock = (
        pook.head(pook.regex(r"https://example.org/\d"))
        .times(len(results))
        .reply(403)
        .mock
    )

    check_dead_links(query_hash, start_slice, results, image_urls)

    assert head_mock.calls == len(results)

    # All the provider's results should be filtered out, leaving only the "other" provider
    assert all([r["provider"] == other_provider for r in results])
