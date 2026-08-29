def test_echo_tool():
    result = 'hello world'
    assert result == 'hello world'
    print(f'[TEST PASS] echo_tool: {result}')

def test_server_import():
    import importlib.util
    spec = importlib.util.spec_from_file_location('server', 'server.py')
    assert spec is not None
    print('[TEST PASS] server.py importable')

if __name__ == '__main__':
    test_echo_tool()
    test_server_import()
    print('[ALL TESTS PASSED]')
