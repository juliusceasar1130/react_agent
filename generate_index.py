import requests
import json
import re
import os

def parse_llms_txt(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return []

    lines = content.split('\n')
    index = []
    current_category = "General"
    
    # Simple heuristic to guess categories if headers exist, 
    # but based on previous view, it's mostly a flat list of links.
    # We will try to infer context or just make a flat list for searching.
    # The file structure seen previously: "- [Title](Link): Description"
    
    # Regex to capture "- [Title](Link): Description" or "- [Title](Link)"
    pattern = re.compile(r'-\s+\[(.*?)\]\((.*?)\)(?::\s*(.*))?')

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for headers to use as categories
        if line.startswith('#'):
            current_category = line.lstrip('#').strip()
            continue

        match = pattern.match(line)
        if match:
            title = match.group(1)
            link = match.group(2)
            desc = match.group(3) if match.group(3) else ""
            
            # Make sure link is absolute
            if not link.startswith('http'):
                # Heuristic: mostly they are relative? content showed full https links
                pass 

            entry = {
                "title": title,
                "url": link,
                "description": desc,
                "category": current_category
            }
            index.append(entry)

    return index

def main():
    url = "https://docs.langchain.com/llms.txt"
    print(f"Fetching {url}...")
    data = parse_llms_txt(url)
    
    output_path = r"d:\Python\workplace\rearch_agent\skills\langchain_expert\resources\langchain_docs_index.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully saved {len(data)} entries to {output_path}")

if __name__ == "__main__":
    main()
