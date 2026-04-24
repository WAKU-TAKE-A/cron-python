import subprocess, sys, os

def run_test():
    # Path to the dummy script
    dummy = os.path.abspath(os.path.join(os.path.dirname(__file__), 'dummy_script.py'))
    # Build the command: python cron_python.py dummy_script.py --once -- '{"msg":"hello"}'
    cmd = [sys.executable, os.path.abspath('..\\cron-python\\cron_python.py'), dummy, '--once', '--', '{"msg":"hello"}']
    result = subprocess.run(cmd, capture_output=True, text=True)
    print('Return code:', result.returncode)
    print('STDOUT:\n', result.stdout)
    print('STDERR:\n', result.stderr)

if __name__ == '__main__':
    run_test()
