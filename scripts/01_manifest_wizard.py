import os
import yaml
import pandas as pd
import argparse

def load_config():
    with open('run_config.yaml', 'r') as f:
        return yaml.safe_load(f)

def save_config(config):
    with open('run_config.yaml', 'w') as f:
        yaml.dump(config, f)

def main():
    parser = argparse.ArgumentParser(description="Filter manifest and configure run")
    parser.add_argument('--manifest', default='manifest.xlsx', help="Path to manifest file")
    parser.add_argument('--auto', action='store_true', help="Run in non-interactive mode using config filters")
    args = parser.parse_args()

    config = load_config()
    manifest_path = args.manifest
    
    if not os.path.exists(manifest_path):
        print(f"Error: Manifest not found at {manifest_path}")
        return

    df = pd.read_excel(manifest_path)
    
    if 'DT' not in df.columns:
        print("Error: Column 'DT' not found in manifest")
        return

    unique_dt = df['DT'].unique().tolist()
    counts = df['DT'].value_counts()
    
    print("Found Document Types (DT):")
    print(counts)
    
    include_dt = config.get('filters', {}).get('dt_include', [])
    exclude_dt = config.get('filters', {}).get('dt_exclude', [])

    if not args.auto:
        # Simple wizard logic (mocked for now as we want to support automation)
        # In a real CLI we would ask for input() but here we stick to config or flags
        # For MVP we just use the config values to filter
        pass

    # Apply filters
    filtered_df = df[df['DT'].isin(include_dt)]
    excluded_df = df[df['DT'].isin(exclude_dt)]
    
    print(f"\nTotal references: {len(df)}")
    print(f"Included: {len(filtered_df)}")
    print(f"Excluded: {len(excluded_df)}")
    
    filtered_df.to_csv('references_filtered.csv', index=False)
    print("Saved references_filtered.csv")

    # Update run log or run_config if needed (idempotent here)
    with open('run_log.md', 'w') as f:
        f.write("# Run Log\n\n")
        f.write(f"Date: {pd.Timestamp.now()}\n")
        f.write(f"Total: {len(df)}\n")
        f.write(f"Included: {len(filtered_df)}\n")
        f.write(f"Excluded: {len(excluded_df)}\n")

if __name__ == "__main__":
    main()
