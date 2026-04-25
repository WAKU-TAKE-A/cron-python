import sys
import time

def main():
    args = sys.argv[1:]
    if not args:
        print("No arguments received")
        return

    command = args[0]
    
    if command == "echo":
        print(" ".join(args[1:]))
    
    elif command == "sleep":
        seconds = float(args[1])
        print(f"Sleeping for {seconds} seconds...")
        time.sleep(seconds)
        print("Finished sleeping")
        
    elif command == "log_heavy":
        # 大量ログ出力テスト（バッファ詰まり確認用）
        for i in range(1000):
            print(f"Line {i}: " + "X" * 100)
            
    elif command == "exit_with":
        sys.exit(int(args[1]))

if __name__ == "__main__":
    main()
