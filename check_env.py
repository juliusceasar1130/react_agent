import sys

def check_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                try:
                    line.decode('ascii')
                except UnicodeDecodeError:
                    print(f"Line {i+1} contains non-ASCII characters:")
                    print(f"  {line.strip()}")
                    for j, byte in enumerate(line):
                        if byte > 127:
                            print(f"    Byte {hex(byte)} at offset {j}")
    except Exception as e:
        print(sys.stderr, e)

if __name__ == "__main__":
    check_file(sys.argv[1])
