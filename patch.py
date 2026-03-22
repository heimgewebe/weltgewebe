import glob

for file in glob.glob('.github/workflows/*.yml'):
    with open(file, 'r') as f:
        content = f.read()

    if "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" not in content:
        content = content.replace("\njobs:\n", "\nenv:\n  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true\n\njobs:\n")

    with open(file, 'w') as f:
        f.write(content)
