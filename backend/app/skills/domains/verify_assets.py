import os
import ast

def check_assets(root_dir):
    missing_files = []
    for root, dirs, files in os.walk(root_dir):
        if 'scenario.py' in files:
            scenario_path = os.path.join(root, 'scenario.py')
            try:
                with open(scenario_path, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                
                # Find SCENARIO assignment
                scenario_data = None
                for node in tree.body:
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == 'SCENARIO':
                                scenario_data = ast.literal_eval(node.value)
                                break
                
                if scenario_data:
                    refs = scenario_data.get('sql_template_refs', []) + scenario_data.get('script_refs', [])
                    for ref in refs:
                        asset_rel_path = ref.get('path')
                        if asset_rel_path:
                            # Usually assets are relative to the scenario directory
                            full_path = os.path.join(root, asset_rel_path)
                            if not os.path.exists(full_path):
                                missing_files.append(f"{scenario_path} -> {full_path}")
            except Exception as e:
                print(f"Error parsing {scenario_path}: {e}")
    
    if missing_files:
        print("Missing assets found:")
        for m in missing_files:
            print(f"  - {m}")
    else:
        print("No missing assets found in scenario files.")

if __name__ == "__main__":
    domains_path = r"f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\backend\app\skills\domains"
    check_assets(domains_path)
