from typing import Union

from arclet.alconna.builtin.construct import AlconnaString, AlconnaFormat
from arclet.alconna.types import AnyStr, AnyDigit
from arclet.alconna import Alconna, Args, Option
from arclet.alconna import command_manager
from arclet.alconna.builtin.actions import store_value
from devtools import debug
from inspect import getsource

print(command_manager)
test_m = AlconnaString("module #测试跨模块")
ping1 = AlconnaString("ping1 <url:url>").reset_namespace("Test")
ping2 = AlconnaString("ping1 <url:url>")

Alconna.set_custom_types(digit=int)

alcf = AlconnaFormat("music {artist} {title} singer {name}")
print(alcf.parse("music --help"))

alc = AlconnaFormat(
    "lp user {target} perm set {perm} {default}",
    {"target": AnyStr, "perm": AnyStr, "default": Args["de":bool:True]},
)
alcc = AlconnaFormat(
    "lp1 user {target}",
    {"target": str}
)

debug(alc)
alc.exception_in_time = False
debug(alc.parse("lp user AAA perm set admin"))

aaa = AlconnaFormat("a {num}", {"num": AnyDigit})
r = aaa.parse("a 1")
print(aaa)
print(r)
print('\n')


def test(wild, text: str, num: int, boolean: bool):
    print('wild:', wild)
    print('text:', text)
    print('num:', num)
    print('boolean:', boolean)


alc1 = AlconnaString(
    "test_type <wild> <text:str> <num:digit> <boolean:bool:False> #测试",
    "--foo <boolean:bool:False> #测试选项",
).set_action(store_value(True))
print(alc1)
print(alc1.get_help())
print(alc1.parse("test_type abcd 'testing a text' 2 --foo"))

print(dir(alc1.action.action.__closure__[0]))
print(getsource(alc1.action.action))

alc2 = Alconna(
    command="test",
    options=[
        Option("foo", Args["bar":str, "bar1":int:12345, "bar2":list])
    ],
    help_text="测试help直接发送"
)
print(alc2.parse("test --help"))

dic = alc1.to_dict()

debug(dic)

dic['headers'] = ['test_type_1']

alc3 = Alconna.from_dict(dic)
print(alc3)
print(alc3.get_help())
print(alc3.parse("test_type_1 abcd 'testing a text' 2 --foo"))

alc4 = Alconna(
    command="test_multi",
    options=[
        Option("--foo", Args["*tags":int:1, "str1":str]),
        Option("--bar", Args["num": int]),
    ]
)

print(alc4.parse("test_multi --foo ab --bar 1"))
alc4.shortcut("st", "test_multi --foo ab --bar 1")
result = alc4.parse("st")
print(result)
print(result.get_first_arg("foo"))

music = AlconnaString(
    "!点歌 <song_name:str>  #在XXX中搜索歌名",  # 主参数: <歌名>
    "--歌手|-s <singer_name:str> #指定歌手"  # 选项名: --歌手  选项别名: -s  选项参数: <歌手名>
)
print(music.get_help())

alc5 = Alconna(
    command="test_anti",
    main_args=Args["!path":int],
)
print(alc5.parse("test_anti a"))


alc6 = Alconna(
    command="test_union",
    main_args=Args.path[Union[int, float]]
)
print(alc6.parse("test_union 12.2"))

alc7 = Alconna(
    command="test_list",
    main_args=Args.seq[list]
)
print(alc7)
print(alc7.parse("test_list \"['1', '2', '3']\""))

alc8 = Alconna(
    command="test_dict",
    main_args=Args.map[dict]
)
print(alc8)
print(alc8.parse("test_dict \"{'a':1, 'b':2}\""))

alc9 = Alconna("test_str", main_args="@foo:str, bar:list, ?baz:int")
print(alc9)
print(alc9.parse("test_str foo=a \"[1]\""))

alc10 = Alconna("test_bool", main_args="foo:str", action=store_value(True))
print(alc10.parse("test_bool a"))