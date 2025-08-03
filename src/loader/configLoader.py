import os
import re
from typing import List

ENV_VARIABLE_PATTERN = re.compile(".*(\\${?([\\w,.]+)}?)")
INTERPOLATION_PATTERN = re.compile(".*(?<!$){([\\w,.]+)}")


class AsClassMember(dict):
    def __getattr__(self, item):
        __value = self.get(item)
        if __value and isinstance(__value, dict):
            __value = AsClassMember(__value)
        return __value


def is_an_env_var(expr):
    try:
        _matched = ENV_VARIABLE_PATTERN.match(expr)
    except Exception as ex:
        raise Exception("Matching variables failed for {} with error {}\n".format(expr, ex))
    return _matched


def need_interpolate_in_list(exprs: List[str]) -> List[str]:
    need_iterp = False
    for expr in exprs:
        need_iterp = need_iterp or need_interpolate(expr)
    return need_iterp


def need_interpolate(expr):
    INTERPOLATION_PATTERN.match(expr)
    try:
        _matched = INTERPOLATION_PATTERN.match(expr)
    except Exception as ex:
        raise Exception("Matching variables failed for {} with error {}\n".format(expr, ex))
    return _matched


def _extract_env_var_name(expr):
    return expr[1:].replace("{", "").replace("}", "") if expr and len(expr) > 1 else ""


def resolve_env_variables(expression):
    if is_an_env_var(expression):
        __v_name = _extract_env_var_name(expression)
        return os.environ.get(__v_name) if __v_name in os.environ else expression
    return expression


def resolve_vars_for_dict_values(in_dict: dict, value_dict: dict) -> dict:
    """
    :param in_dict: input_dict which contains $XYZ or ${XYZ} and will be resolved to the real value defined in value_dict
    :param value_dict: Name/Value pairs predefined used to replace in_dict's env-variable(placeholders)
    :return: in_dict with placeholders being resolved to real value
    """
    for (_key, _val) in in_dict.items():
        in_dict[_key] = resolve_variables_value(_val, value_dict)
    return in_dict


def resolve_variables_value(expr, value_dict):
    _replacing = True

    while _replacing:
        _replacing = False

        _matched = is_an_env_var(expr)
        if _matched:
            _replacing = True
            _prefix = _matched.group(1)
            _v_name = _matched.group(2)
            if not _v_name:
                raise Exception("Invalid variable definition in string:" + expr)

            if _v_name in value_dict:
                if isinstance(value_dict[_v_name], dict):
                    if expr.replace(_prefix, "") == "":
                        return resolve_vars_for_dict_values(value_dict[_v_name], value_dict)
                    else:
                        raise Exception("The variable {} is a dict, cannot replace it in {}".format(_v_name, expr))
                else:
                    expr = expr.replace(_prefix, value_dict[_v_name])
            elif _v_name in os.environ:
                expr = expr.replace(_v_name, os.environ[_v_name])
            else:
                raise Exception(f"Cannot find the definition of the variable:{_v_name} for {expr}")
        else:
            return expr.format(**value_dict) if need_interpolate(expr) else expr


def get_resolved_dict_values(conf_dict: dict, value_dict: dict) -> dict[str, any]:
    resolved_dict_values = {}

    for key, value in conf_dict.items():
        if isinstance(value, str):
            _resolved = resolve_variables_value(value, value_dict)
            if need_interpolate(_resolved):
                _resolved = _resolved.format(**value_dict)
            resolved_dict_values[key] = _resolved
        elif isinstance(value, dict):
            """
            recursive call
            """
            resolved_dict_values[key] = get_resolved_dict_values(value, value_dict)
        else:
            resolved_dict_values[key] = value
    return resolved_dict_values


class ConfigLoader:
    def __init__(self, config_file, file_loader: callable, var_prefix: str = ""):
        self.__config_file = config_file
        self.__file_loader = file_loader
        self.__variables: dict = {}
        self.__configs: dict = {}
        self.__base_dir = os.path.dirname(config_file)
        self.__var_prefix = var_prefix

    @property
    def variables(self):
        return self.__variables

    @property
    def configs(self):
        return self.__configs

    def load_with_variables(self) -> dict:
        conf = {}
        self.__configs = self.load()

        conf.update(self.__configs)
        conf['variables'] = self.__variables
        return conf

    def load(self):
        self.__configs = self.read_config_file(self.__config_file)
        if not self.__configs:
            self.__configs = dict()
        self.__init_variables()
        return self._variables_resolved_dict(self.__configs, self.__variables)

    def __init_variables(self):
        self.__variables = self._parse_included_variables()
        self.__compile_variables()

    def __compile_variables(self):
        _variables = dict()
        if self.__variables:
            for v_name, v_value in self.__variables.items():
                if type(v_value) is str and v_value.startswith(self.__var_prefix):
                    v_value = resolve_variables_value(v_value, self.__variables)
                _variables[v_name] = v_value
        self.__variables.update(_variables)

    def read_config_file(self, config_file):
        if not os.path.isfile(config_file):
            raise FileExistsError(f'Config file: {config_file} does not exist')

        with open(config_file, "r") as f:
            try:
                return self.__file_loader(f)
            except yaml.YAMLError as ex:
                print(f"Error: unable to load {config_file}")
                raise ex

    def _parse_included_variables(self):
        return self.get_included_variables((self.__configs["includes"] if "includes" in self.__configs else []))

    def get_included_variables(self, includes_file, path: str = None):
        if isinstance(includes_file, list):
            _variables = {}
            for _file in includes_file:
                _variables.update(self.get_variables_from_file(_file, path))
            return _variables
        else:
            return self.get_included_variables([includes_file], path)

    def get_variables_from_file(self, file: str, path: str):
        _variables = {}
        _included_file: str = resolve_variables_value(file, self.__variables)
        if not _included_file.startswith("/"):
            if not path:
                path = self.__base_dir
            _included_file = os.path.join(path, _included_file)

        with open(_included_file, "r") as stream:
            _tmp_configs = self.__file_loader(stream)
            if "variables" in _tmp_configs:
                for v_name, v_value in _tmp_configs["variables"].items():
                    _variables[v_name] = resolve_variables_value(v_value, os.environ) if isinstance(v_value,
                                                                                                    str) else v_value

            if "includes" in _tmp_configs:
                _variables.update(self.get_included_variables(
                    includes_file=_tmp_configs["includes"],
                    path=os.path.dirname(_included_file))
                )

        return _variables

    def _variables_resolved_dict(self, conf_dict: dict, variables_dict: dict) -> dict:
        resolved_dict = dict()
        for key, value in conf_dict.items():
            if isinstance(value, str):
                resolved_dict[key] = resolve_variables_value(value, variables_dict)
            elif isinstance(value, dict):
                resolved_dict[key] = self._variables_resolved_dict(value, variables_dict)
            else:
                if isinstance(value, list):
                    value = [_v.format(**variables_dict) if need_interpolate(_v) else _v for _v in value]
                elif isinstance(value, str) and need_interpolate(value):
                    value = value.format(**variables_dict)
                resolved_dict[key] = value
        return resolved_dict
