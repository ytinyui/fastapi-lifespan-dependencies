from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from fastapi_lifespan_dependencies import Lifespan

lifespan = Lifespan()


async def dependency() -> AsyncIterator[int]:
    yield 0


async def function_dependency() -> int:
    return 0


@lifespan.register
async def lifespan_dependency() -> AsyncIterator[int]:
    yield 1


@lifespan.register
async def lifespan_function_dependency() -> int:
    return 1


@lifespan.register
async def sync_lifespan_dependency() -> AsyncIterator[int]:
    yield 2


@lifespan.register
def lifespan_sync_function_dependency() -> int:
    return 2


@lifespan.register
async def dependent(
    value: Annotated[int, Depends(dependency)],
) -> AsyncIterator[int]:
    yield value


@lifespan.register
async def function_dependant(
    value: Annotated[int, Depends(function_dependency)],
) -> int:
    return value


@lifespan.register
async def lifespan_dependent(
    value: Annotated[int, Depends(lifespan_dependency)],
) -> AsyncIterator[int]:
    yield value


@lifespan.register
async def lifespan_function_dependent(
    value: Annotated[int, Depends(lifespan_function_dependency)],
) -> int:
    return value


# TODO: Test async/sync dependency chains?
