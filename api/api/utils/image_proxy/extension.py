from os.path import splitext
from urllib.parse import urlparse

import aiohttp
import django_redis
import sentry_sdk
from asgiref.sync import sync_to_async

from api.utils.aiohttp import get_aiohttp_session
from api.utils.asyncio import do_not_wait_for
from api.utils.image_proxy.exception import UpstreamThumbnailException


_HEAD_TIMEOUT = aiohttp.ClientTimeout(10)


async def get_image_extension(image_url: str, media_identifier) -> str | None:
    cache = django_redis.get_redis_connection("default")
    key = f"media:{media_identifier}:thumb_type"

    ext = _get_file_extension_from_url(image_url)

    if not ext:
        # If the extension is not present in the URL, try to get it from the redis cache
        ext = await sync_to_async(cache.get)(key)
        ext = ext.decode("utf-8") if ext else None

    if not ext:
        # If the extension is still not present, try getting it from the content type
        try:
            session = await get_aiohttp_session()
            response = await session.head(image_url, timeout=_HEAD_TIMEOUT)
            response.raise_for_status()
            if response.headers and "Content-Type" in response.headers:
                content_type = response.headers["Content-Type"]
                ext = _get_file_extension_from_content_type(content_type)
            else:
                ext = None

            do_not_wait_for(sync_to_async(cache.set)(key, ext if ext else "unknown"))
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise UpstreamThumbnailException(
                "Failed to render thumbnail due to inability to check media "
                f"type. {exc}"
            )

    return ext


def _get_file_extension_from_url(image_url: str) -> str:
    """Return the image extension if present in the URL."""
    parsed = urlparse(image_url)
    _, ext = splitext(parsed.path)
    return ext[1:].lower()  # remove the leading dot


def _get_file_extension_from_content_type(content_type: str) -> str | None:
    """
    Return the image extension if present in the Response's content type
    header.
    """
    if content_type and "/" in content_type:
        return content_type.split("/")[1]
    return None
