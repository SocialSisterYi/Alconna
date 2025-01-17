from typing import Literal, Dict, Callable, Optional, Coroutine, Union, AsyncIterator, TypedDict
import asyncio

from arclet.alconna import Alconna
from arclet.alconna.arpamar import Arpamar
from arclet.alconna.proxy import AlconnaMessageProxy
from arclet.alconna.manager import command_manager

from graia.broadcast.entities.event import Dispatchable
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.utilles import run_always_await_safely
from graia.broadcast import Force

from graia.ariadne import get_running
from graia.ariadne.app import Ariadne
from graia.ariadne.dispatcher import ContextDispatcher
from graia.ariadne.event.message import GroupMessage, MessageEvent
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Quote
from graia.ariadne.util import resolve_dispatchers_mixin

from .proxy import GraiaAlconnaPropetry


class AriadneAMP(AlconnaMessageProxy):
    pre_treatments: Dict[Alconna, Callable[
        [MessageChain, Arpamar, Optional[str], Optional[MessageEvent]],
        Coroutine[None, None, GraiaAlconnaPropetry]
    ]]

    def add_proxy(
            self,
            command: Union[str, Alconna],
            pre_treatment: Optional[
                Callable[
                    [MessageChain, Arpamar, Optional[str], Optional[MessageEvent]],
                    Coroutine[None, None, GraiaAlconnaPropetry]
                ]
            ] = None,
    ):
        if isinstance(command, str):
            command = command_manager.get_command(command)  # type: ignore
            if not command:
                raise ValueError(f'Command {command} not found')
        self.pre_treatments.setdefault(command, pre_treatment or self.default_pre_treatment)  # type: ignore

    async def fetch_message(self) -> AsyncIterator[MessageChain]:
        pass

    @staticmethod
    def later_condition(result: GraiaAlconnaPropetry) -> bool:
        return True


class AlconnaHelpDispatcher(BaseDispatcher):
    mixin = [ContextDispatcher]

    def __init__(self, alconna: "Alconna", help_string: str, source_event: MessageEvent):
        self.command = alconna
        self.help_string = help_string
        self.source_event = source_event

    async def catch(self, interface: "DispatcherInterface"):
        if interface.name == "help_string" and interface.annotation == str:
            return self.help_string
        if isinstance(interface.annotation, Alconna):
            return self.command
        if issubclass(interface.annotation, MessageEvent) or interface.annotation == MessageEvent:
            return self.source_event


class AlconnaHelpMessage(Dispatchable):
    """
    Alconna帮助信息发送事件
    如果触发的某个命令的帮助选项, 当AlconnaDisptcher的reply_help为False时, 会发送该事件
    """

    command: "Alconna"
    """命令"""

    help_string: str
    """帮助信息"""

    source_event: MessageEvent
    """来源事件"""


class _AlconnaLocalStorage(TypedDict):
    alconna_result: GraiaAlconnaPropetry


class AlconnaDispatcher(BaseDispatcher):
    proxy = AriadneAMP(loop=asyncio.get_event_loop())

    def __init__(
            self,
            *,
            alconna: "Alconna",
            help_flag: Literal["reply", "post", "stay"] = "stay",
            skip_for_unmatch: bool = True,
            help_handler: Optional[Callable[[str], MessageChain]] = None,
            allow_quote: bool = False,
    ):
        """
        构造 Alconna调度器
        Args:
            alconna (Alconna): Alconna实例
            help_flag ("reply", "post", "stay"): 帮助信息发送方式
            skip_for_unmatch (bool): 当指令匹配失败时是否跳过对应的事件监听器, 默认为 True
            allow_quote (bool): 是否允许引用回复消息触发对应的命令, 默认为 False
        """
        super().__init__()
        self.command = alconna
        self.help_flag = help_flag
        self.skip_for_unmatch = skip_for_unmatch
        self.help_handler = help_handler or (lambda x: MessageChain.create(x))
        self.allow_quote = allow_quote

    async def beforeExecution(self, interface: DispatcherInterface):
        event: MessageEvent = interface.event
        app: Ariadne = get_running()

        async def reply_help_message(
                origin: MessageChain,
                result: Arpamar,
                help_text: Optional[str] = None,
                source: Optional[MessageEvent] = None,
        ):

            if result.matched is False and help_text:
                if self.help_flag == "reply":
                    help_text = await run_always_await_safely(self.help_handler, help_text)
                    if isinstance(source, GroupMessage):
                        await app.sendGroupMessage(source.sender.group, help_text)
                    else:
                        await app.sendMessage(source.sender, help_text)
                    return GraiaAlconnaPropetry(origin, result, None, source)
                if self.help_flag == "post":
                    dispatchers = resolve_dispatchers_mixin(
                        [AlconnaHelpDispatcher(self.command, help_text, source), source.Dispatcher]
                    )
                    for listener in interface.broadcast.default_listener_generator(AlconnaHelpMessage):
                        await interface.broadcast.Executor(listener, dispatchers=dispatchers)
                    return GraiaAlconnaPropetry(origin, result, None, source)
            return GraiaAlconnaPropetry(origin, result, help_text, source)

        message: MessageChain = await interface.lookup_param("message", MessageChain, None)
        if not self.allow_quote and message.has(Quote):
            raise ExecutionStop
        self.proxy.add_proxy(self.command, reply_help_message)
        await self.proxy.push_message(message, event, self.command)
        local_storage: _AlconnaLocalStorage = interface.local_storage  # type: ignore
        local_storage['alconna_result'] = await self.proxy.export_results.get()

    async def catch(self, interface: DispatcherInterface):
        local_storage: _AlconnaLocalStorage = interface.local_storage
        res = local_storage['alconna_result']
        if not res.result.matched and not res.help_text:
            if "-h" in str(res.origin):
                raise ExecutionStop
            if self.skip_for_unmatch:
                raise ExecutionStop

        if interface.annotation == GraiaAlconnaPropetry:
            return res
        if interface.annotation == Arpamar:
            return res.result
        if interface.annotation == str and interface.name == "help_text":
            return res.help_text
        if issubclass(interface.annotation, MessageEvent) or interface.annotation == MessageEvent:
            return Force(res.source)
