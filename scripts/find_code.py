import sys
import os

search_dir = sys.argv[1]

for root, dirs, files in os.walk(search_dir):
    for file in files:
        if file.endswith(('.ts', '.tsx', '.py', '.js', '.jsx')):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    if 'delete' in content.lower() and ('job' in content.lower() or 'dataset' in content.lower()):
                        print(f"Found match in {filepath}")
            except Exception as e:
                pass
