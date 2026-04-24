import sys

def main():
    print(f"Number of arguments: {len(sys.argv) - 1}")
    for i, arg in enumerate(sys.argv[1:], 1):
        print(f"Argument {i}: {arg}")

if __name__ == "__main__":
    main()
