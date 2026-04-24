import sys, json

def main():
    # Print received args for verification
    print('ARGS:', sys.argv[1:])
    # If a JSON argument is provided, try to parse it
    if len(sys.argv) > 1:
        try:
            data = json.loads(sys.argv[1])
            print('JSON:', data)
        except json.JSONDecodeError:
            print('INVALID JSON')

if __name__ == '__main__':
    main()
