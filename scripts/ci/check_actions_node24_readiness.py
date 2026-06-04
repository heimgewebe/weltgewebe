import yaml
import glob
import sys

def check_workflows():
    workflows = glob.glob('.github/workflows/*.yml') + glob.glob('.github/workflows/*.yaml')
    issues = []
    reusable_calls = []

    js_actions = [
        'actions/checkout',
        'actions/setup-node',
        'actions/cache',
        'actions/upload-artifact',
        'actions/download-artifact',
        'pnpm/action-setup',
        'actions/setup-python',
        'astral-sh/setup-uv',
        'extractions/setup-just',
        'DavidAnson/markdownlint-cli2-action',
        'lycheeverse/lychee-action',
        'docker/setup-buildx-action',
        'softprops/action-gh-release',
        'anchore/sbom-action',
        'dorny/paths-filter'
    ]

    print("| Workflow File | Job Name | Action Uses | Tag/SHA | JS Action? | Has FORCE_NODE24? |")
    print("|---------------|----------|-------------|---------|------------|-------------------|")

    for wf_file in workflows:
        with open(wf_file, 'r') as f:
            try:
                wf = yaml.safe_load(f)
            except yaml.YAMLError as e:
                print(f"Error parsing {wf_file}: {e}", file=sys.stderr)
                continue

            if not wf: continue

            wf_env = wf.get('env', {})
            has_wf_node24 = str(wf_env.get('FORCE_JAVASCRIPT_ACTIONS_TO_NODE24', '')).lower() == 'true'

            jobs = wf.get('jobs', {})
            for job_name, job in jobs.items():
                if not isinstance(job, dict): continue

                # Check for reusable workflow calls
                if 'uses' in job:
                    uses_ref = job['uses']
                    reusable_calls.append(f"{wf_file} {job_name} -> {uses_ref}")
                    continue

                job_env = job.get('env', {})
                has_job_node24 = str(job_env.get('FORCE_JAVASCRIPT_ACTIONS_TO_NODE24', '')).lower() == 'true'
                has_node24 = has_wf_node24 or has_job_node24

                steps = job.get('steps', [])
                if not isinstance(steps, list): continue

                for step in steps:
                    uses = step.get('uses')
                    if uses:
                        action_base = uses.split('@')[0]
                        is_js = any(action_base.startswith(js) for js in js_actions)
                        if is_js:
                            is_sha = len(uses.split('@')[1]) == 40
                            print(f"| {wf_file} | {job_name} | {uses} | {'SHA' if is_sha else 'Tag'} | Yes | {'Yes' if has_node24 else 'No'} |")
                            if not has_node24:
                                issues.append(f"{wf_file} - {job_name}: Missing FORCE_JAVASCRIPT_ACTIONS_TO_NODE24")

    if reusable_calls:
        print("\nReusable workflow calls detected; caller env does not prove called workflow Node-24 readiness:")
        for call in reusable_calls:
            print(f"- {call}")

    return issues

if __name__ == '__main__':
    issues = check_workflows()
    if issues:
        print("\nFound issues:")
        for issue in issues:
            print(f"- {issue}")
        sys.exit(1)
    else:
        print("\nAll good!")
        sys.exit(0)
