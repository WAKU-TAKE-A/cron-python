import sys
import json
import time

def main():
    if len(sys.argv) < 2:
        print("Error: No arguments provided.")
        sys.exit(1)
        
    try:
        args_str = sys.argv[1]
        args_json = json.loads(args_str)
        print(f"Received arguments: {args_json}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)
        
    duration = args_json.get("duration", 1)
    print(f"Simulating work for {duration} seconds...")
    time.sleep(duration)
    
    print("Work completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
