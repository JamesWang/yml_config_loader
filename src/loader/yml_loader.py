import os

import yaml

from src.loader.configLoader import resolve_env_variables, ConfigLoader


def join(yml_loader, node):
    _items = yml_loader.construct_sequence(node)
    _resolved_items = [resolve_env_variables(str(expr)) for expr in _items]
    return "".join(_resolved_items)


yaml.SafeLoader.add_constructor("!join", join)


def read_config_file(config_file):
    if not os.path.isfile(config_file):
        raise FileExistsError(f'Config file: {config_file} does not exist')

    with open(config_file, "r") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as ex:
            print(f"Error: unable to load {config_file}")
            raise ex


if __name__ == "__main__":
    config_loader = ConfigLoader(
        config_file="../../test/input/example_config.yaml",
        file_loader=yaml.safe_load
    )
    v = config_loader.load(read_config_file)
    print(v)