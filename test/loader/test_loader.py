from src.loader.configLoader import is_an_env_var


def test_is_an_env_var_true():
    an_env_var = "${TEST_DIR}/abc"
    assert is_an_env_var(an_env_var)


def test_is_an_env_var_false():
    an_env_var = "/abc/efg/123"
    assert not is_an_env_var(an_env_var)


if __name__ == "__main__":
    test_is_an_env_var_true()
    test_is_an_env_var_false()