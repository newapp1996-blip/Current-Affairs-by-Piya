def update_output_files(data_dict):
    """
    Saves JSON data to data.json and updates index.html safely
    without regex backslash escape errors.
    """
    # 1. Output data.json for fetch requests
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2)
    print("Updated data.json successfully!")

    # 2. Inject into index.html safely
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()

        json_str = json.dumps(data_dict, indent=2)
        replacement = f'const appData = {json_str};'

        # Using a lambda function prevents Python re.sub from evaluating \ escapes
        updated_html = re.sub(
            r'(const|let|var)\s+appData\s*=\s*\{.*?\};',
            lambda m: replacement,
            html_content,
            flags=re.DOTALL
        )

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(updated_html)
        print("Updated index.html successfully!")
        
