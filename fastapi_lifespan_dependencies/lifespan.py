from asyncio import Task, TaskGroup
from collections.abc import AsyncIterator, Awaitable, Iterator, Mapping
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
    contextmanager,
)
from inspect import isasyncgenfunction, isgeneratorfunction
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.concurrency import contextmanager_in_threadpool
from fastapi.dependencies.utils import (
    get_dependant,
    solve_dependencies,
)
from starlette.requests import HTTPConnection, Request

from fastapi_lifespan_dependencies.exceptions import LifespanDependencyError

LifespanDependency = Callable[
    ..., AbstractAsyncContextManager[Any] | AbstractContextManager[Any]
]


async def _run_dependency[R](
    exit_stack: AsyncExitStack,
    solved_dependency: AbstractAsyncContextManager[R] | AbstractContextManager[R],
) -> R:
    return await exit_stack.enter_async_context(
        solved_dependency
        if isinstance(solved_dependency, AbstractAsyncContextManager)
        else contextmanager_in_threadpool(solved_dependency)
    )


class Lifespan:
    def __init__(self) -> None:
        self.dependencies: dict[str, LifespanDependency] = {}
        self.tasks: dict[str, Task[Any]] = {}

    @asynccontextmanager
    async def __call__(self, app: FastAPI) -> AsyncIterator[Mapping[str, Any]]:
        state: dict[str, Any] = {}

        async with AsyncExitStack() as exit_stack:

            async def init_dependency(name: str, dependency: Callable[..., Any]):
                dependant = get_dependant(path="", call=dependency)
                initial_state_request = Request(
                    scope={
                        "type": "http",
                        "query_string": "",
                        "headers": "",
                        "state": state,
                    }
                )

                (
                    solved_values,
                    errors,
                    background_tasks,
                    *_,
                ) = await solve_dependencies(
                    request=initial_state_request,
                    dependant=dependant,
                    async_exit_stack=exit_stack,
                )

                if background_tasks is not None:
                    raise LifespanDependencyError(
                        "BackgroundTasks are unavailable during startup"
                    )

                if len(errors) > 0:
                    raise LifespanDependencyError(errors)

                state[name] = await _run_dependency(
                    exit_stack, dependency(**solved_values)
                )

            async with TaskGroup() as group:
                for name, dependency in self.dependencies.items():
                    self.tasks[name] = group.create_task(
                        init_dependency(name, dependency)
                    )
            yield state

    def register[R](
        self, dependency: Callable[..., AsyncIterator[R] | Iterator[R]]
    ) -> Callable[[HTTPConnection], Awaitable[R]]:
        if isasyncgenfunction(dependency):
            context_manager = asynccontextmanager(dependency)
        elif isgeneratorfunction(dependency):
            context_manager = contextmanager(dependency)
        else:
            raise TypeError(f"{dependency.__name__} is not a context manager")

        name = f"{dependency.__module__}.{dependency.__qualname__}"
        self.dependencies[name] = context_manager

        async def path_dependency(connection: HTTPConnection) -> Any:
            if not hasattr(connection.state, name):
                await self.tasks[name]
            return getattr(connection.state, name)

        return path_dependency
