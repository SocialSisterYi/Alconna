import abc
import asyncio
import inspect
from asyncio.queues import Queue
from functools import lru_cache
from typing import Optional, Union, Callable, Dict, AsyncIterator, Coroutine, Any, Tuple
from .types import DataCollection
from .main import Alconna
from .arpamar import Arpamar
from .manager import command_manager
from .builtin.actions import require_help_send_action


@lru_cache(4096)
def iscoroutinefunction(o):
    return inspect.iscoroutinefunction(o)


async def run_always_await(callable_target, *args, **kwargs):
    if iscoroutinefunction(callable_target):
        return await callable_target(*args, **kwargs)
    return callable_target(*args, **kwargs)


class AlconnaProperty:
    """对解析结果的封装"""

    def __init__(
            self,
            origin: Union[str, DataCollection],
            result: Arpamar,
            help_text: Optional[str] = None,
            source: Optional[Any] = None,
    ):
        self.origin = origin
        self.result = result
        self.help_text = help_text
        self.source = source


class AlconnaMessageProxy(metaclass=abc.ABCMeta):
    """消息解析的代理"""
    loop: asyncio.AbstractEventLoop
    export_results: Queue
    pre_treatments: Dict[Alconna, Callable[[Union[str, DataCollection], Arpamar, Optional[str]], AlconnaProperty]]

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.pre_treatments = {}
        try:
            self.export_results = Queue(loop=self.loop)
        except TypeError:
            self.export_results = Queue()
        self.default_pre_treatment = lambda o, r, h, s: AlconnaProperty(o, r, h, s)

    def add_proxy(
            self,
            command: Union[str, Alconna],
            pre_treatment: Optional[
                Callable[[Union[str, DataCollection], Arpamar, Optional[str]],
                         Union[AlconnaProperty, Coroutine[None, None, AlconnaProperty]]]
            ] = None,
    ):
        if isinstance(command, str):
            command = command_manager.get_command(command)  # type: ignore
            if not command:
                raise ValueError(f'Command {command} not found')
        self.pre_treatments.setdefault(command, pre_treatment or self.default_pre_treatment)  # type: ignore

    @abc.abstractmethod
    async def fetch_message(self) -> AsyncIterator[Tuple[Union[str, DataCollection], Any]]:
        """主动拉取消息"""
        yield NotImplemented
        raise NotImplementedError

    @staticmethod
    def later_condition(result: AlconnaProperty) -> bool:
        if not result.result.matched and not result.help_text:
            return False
        return True

    async def push_message(
            self,
            message: Union[str, DataCollection],
            source: Optional[Any] = None,
            command: Optional[Alconna] = None,
    ):
        async def __exec(_command, _treatment):
            may_help_text = None

            def _h(string):
                nonlocal may_help_text
                may_help_text = string

            require_help_send_action(_h, _command.name)

            _res = _command.parse(message)
            _property = await run_always_await(_treatment, message, _res, may_help_text, source)
            if not self.later_condition(_property):
                return
            await self.export_results.put(_property)
        if command and command in self.pre_treatments:
            await __exec(command, self.pre_treatments[command])
        else:
            for command, treatment in self.pre_treatments.items():
                await __exec(command, treatment)

    async def run(self):
        async for message, source in self.fetch_message():
            await self.push_message(message, source)

    def run_blocking(self):
        self.loop.run_until_complete(self.run())
