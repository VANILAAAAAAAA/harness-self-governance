from pathlib import Path
from graph_harness_maintain.policy import Policy, looks_absolute_path
from graph_harness_maintain.store import GraphStore
F=Path(__file__).parent/'fixtures'

def test_policy_defaults_and_output_scope():
    p=Policy('lab', repo_root=str(Path(__file__).parents[1]))
    assert p.mode=='report_only'
    assert p.check_mode_command('validate').allowed
    assert not p.check_mode_command('apply').allowed
    assert not p.check_output_path(str(F/'graph.jsonl')).allowed
    assert p.check_output_path(str(Path(__file__).parents[1]/'artifacts'/'x.json')).allowed

def test_profile_boundary_sensitive_export_block():
    s=GraphStore.from_paths(str(F/'synthetic_graph.jsonl'), str(F/'synthetic_events.jsonl'), str(F/'synthetic_schema.yaml'))
    p=Policy('lab')
    assert not p.check_export_node(s.nodes['raw:private_table']).allowed

def test_looks_absolute_path_detects_anchored_and_embedded_paths():
    unsafe = [
        '/home/example/private',
        'prefix /home/example/private suffix',
        '/mnt/c/Users/example/file.txt',
        'prefix /mnt/d/ehr/file.csv suffix',
        '/tmp/graph-harness-secret',
        'prefix /tmp/graph-harness-secret suffix',
        r'C:\\Users\\example\\file.txt',
        r'prefix C:\\Users\\example\\file.txt suffix',
        r'\\wsl$\\Ubuntu\\home\\example\\file.txt',
        r'prefix \\wsl.localhost\\Ubuntu\\home\\example\\file.txt suffix',
        'file:///home/example/private',
        'file:///C:/Users/example/file.txt',
        '/opt/unrecognized/absolute/path',
        'prefix /var/lib/private suffix',
    ]
    for value in unsafe:
        assert looks_absolute_path(value), value

def test_looks_absolute_path_allows_relative_and_identifiers():
    safe = ['relative/path', 'node:abc', 'capability summary', 'not/a/rooted/path', 'C:relative']
    for value in safe:
        assert not looks_absolute_path(value), value
