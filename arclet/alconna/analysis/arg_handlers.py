from typing import Union, Dict, Any, Iterable

from ..types import MultiArg, ArgPattern, NonTextElement, PatternToken, AntiArg
from ..analysis.analyser import Analyser
from ..exceptions import ParamsUnmatched


def multi_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, NonTextElement],
        key: str,
        value: MultiArg,
        default: Any,
        nargs: int,
        sep: str,
        result_dict: Dict[str, Any]
):
    _m_arg_base = value.arg_value
    if _m_arg_base.__class__ is ArgPattern:
        if not isinstance(may_arg, str):
            return
    elif isinstance(may_arg, str):
        return
    # 当前args 已经解析 m 个参数， 总共需要 n 个参数，总共剩余p个参数，
    # q = n - m 为剩余需要参数（包括自己）， p - q + 1 为自己可能需要的参数个数
    _m_rest_arg = nargs - len(result_dict) - 1
    _m_all_args_count = analyser.rest_count(sep) - _m_rest_arg + 1
    analyser.reduce_data(may_arg)
    result = []

    def __putback(data):
        analyser.reduce_data(data)
        for ii in range(min(len(result), _m_rest_arg)):
            analyser.reduce_data(result.pop(-1))

    for i in range(_m_all_args_count):
        _m_arg = analyser.next_data(sep)
        if isinstance(_m_arg, str) and _m_arg in analyser.params:
            __putback(_m_arg)
            break
        if _m_arg_base.__class__ is ArgPattern:
            if not isinstance(_m_arg, str):
                __putback(_m_arg)
                break
            _m_arg_find = _m_arg_base.find(_m_arg)
            if not _m_arg_find:
                __putback(_m_arg)
                if default is None:
                    raise ParamsUnmatched(f"param {may_arg} is incorrect")
                result = [default]
                break
            if may_arg == _m_arg_base.pattern:
                _m_arg_find = Ellipsis
            if _m_arg_base.token == PatternToken.REGEX_TRANSFORM and isinstance(_m_arg_find, str):
                _m_arg_find = _m_arg_base.transform_action(_m_arg_find)
            result.append(_m_arg_find)
        else:
            if isinstance(_m_arg, str):
                __putback(_m_arg)
                break
            if _m_arg.__class__ is _m_arg_base:
                result.append(_m_arg)
            elif default is not None:
                __putback(_m_arg)
                result = [default]
                break
            else:
                __putback(_m_arg)
                raise ParamsUnmatched(f"param type {_m_arg.__class__} is incorrect")
    result_dict[key] = result


def anti_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, NonTextElement],
        key: str,
        value: AntiArg,
        default: Any,
        nargs: int,
        sep: str,
        result_dict: Dict[str, Any]
):
    _a_arg_base = value.arg_value
    if _a_arg_base.__class__ is ArgPattern:
        arg_find = _a_arg_base.find(may_arg)
        if not arg_find and isinstance(may_arg, str):
            result_dict[key] = may_arg
        else:
            analyser.reduce_data(may_arg)
            if default is None:
                raise ParamsUnmatched(f"param {may_arg} is incorrect")
            result_dict[key] = default
    elif isinstance(_a_arg_base, Iterable):
        if may_arg in _a_arg_base:
            analyser.reduce_data(may_arg)
            if default is None:
                raise ParamsUnmatched(f"param {may_arg} is incorrect")
            may_arg = default
        result_dict[key] = may_arg
    else:
        if may_arg.__class__ is not _a_arg_base:
            result_dict[key] = may_arg
        elif default is not None:
            result_dict[key] = default
            analyser.reduce_data(may_arg)
        else:
            analyser.reduce_data(may_arg)
            if may_arg:
                raise ParamsUnmatched(f"param type {may_arg.__class__} is incorrect")
            else:
                raise ParamsUnmatched(f"param {key} is required")


def common_arg_handler(
        analyser: Analyser,
        may_arg: Union[str, NonTextElement],
        key: str,
        value: ArgPattern,
        default: Any,
        nargs: int,
        sep: str,
        result_dict: Dict[str, Any]
):
    arg_find = value.find(may_arg)
    if not arg_find:
        analyser.reduce_data(may_arg)
        if default is None:
            if may_arg:
                raise ParamsUnmatched(f"param {may_arg} is incorrect")
            else:
                raise ParamsUnmatched(f"param {key} is required")
        arg_find = default
    if may_arg == value.pattern:
        arg_find = Ellipsis
    if value.token == PatternToken.REGEX_TRANSFORM and isinstance(arg_find, str):
        arg_find = value.transform_action(arg_find)
    result_dict[key] = arg_find
