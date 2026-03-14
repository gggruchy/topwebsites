import sys
import os
import re
from collections import defaultdict
from typing import List

def validate_limits(instruction: str) -> bool:
    if len(instruction) > 500: return False
    if instruction.count('*') > 2: return False
    if instruction.count('^') > 2: return False
    return True

def is_structural_safe(instruction: str) -> bool:
    """Blocks regex mutation of Goggles-specific structural operators."""
    if instruction.startswith('/') and instruction.endswith('/'): return False
    if any(op in instruction for op in ['||', '@@', '|', '$']): return False
    return True

def translate_to_regex(token: str) -> str:
    escaped = re.escape(token)
    escaped = escaped.replace(r'\*', '.*')
    # TARGET_LOCK: Apply strict raw string prefix (r'') to the replacement payload
    escaped = escaped.replace(r'\^', r'(?:[^a-zA-Z0-9_%\.-]|$)')
    return escaped

def pack_regex_nodes(prefix: str, suffixes: set) -> List[str]:
    if not suffixes or suffixes == {""}: 
        raw_rule = prefix if suffixes == {""} else f"{prefix}/"
        return [raw_rule] if validate_limits(raw_rule) else []
        
    if len(suffixes) == 1:
        raw_rule = f"{prefix}/{list(suffixes)[0]}"
        return [raw_rule] if validate_limits(raw_rule) else []
        
    packed_rules = []
    current_group = []
    base_escaped_prefix = translate_to_regex(prefix)
    
    def compile_group(grp: List[str]) -> str:
        if len(grp) == 1: return f"{prefix}/{grp[0]}"
        joined = "|".join(translate_to_regex(s) for s in grp)
        return f"/{base_escaped_prefix}\\/({joined})/"

    for suffix in sorted(suffixes):
        current_group.append(suffix)
        test_rule = compile_group(current_group)
        
        if not validate_limits(test_rule):
            current_group.pop()
            if current_group:
                packed_rules.append(compile_group(current_group))
            current_group = [suffix]
            
    if current_group:
        packed_rules.append(compile_group(current_group))
        
    return packed_rules

def execute_tier1_chunking(input_file: str):
    MAX_LINES = 100000
    MAX_BYTES = 1900000
    NEWLINE_BYTES = len(os.linesep.encode('utf-8'))
    BATCH_LIMIT = 250000
    
    if not os.path.exists(input_file):
        print(f"ERROR: Target '{input_file}' not found.")
        sys.exit(1)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    chunk_index = 1
    current_lines = 0
    current_bytes = 0
    file_pointer = None
    
    def rotate_io():
        nonlocal file_pointer, chunk_index, current_lines, current_bytes
        if file_pointer: file_pointer.close()
        file_pointer = open(f"{base_name}_part{chunk_index}.goggles", 'w', encoding='utf-8', newline='\n')
        chunk_index += 1
        current_lines = 0
        current_bytes = 0

    def flush_batch(batch_map: dict, unmergeable_list: List[str]):
        nonlocal current_lines, current_bytes
        
        def write_rule(rule: str):
            nonlocal current_lines, current_bytes
            rule_bytes = len(rule.encode('utf-8')) + NEWLINE_BYTES
            if current_lines >= MAX_LINES or (current_bytes + rule_bytes) > MAX_BYTES:
                rotate_io()
            file_pointer.write(rule + '\n')
            current_lines += 1
            current_bytes += rule_bytes

        for rule in unmergeable_list:
            write_rule(rule)

        for pfx, sfx_set in batch_map.items():
            for rule in pack_regex_nodes(pfx, sfx_set):
                write_rule(rule)

    rotate_io()
    prefix_map = defaultdict(set)
    unmergeable = []
    line_count = 0

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith('!'): continue
            if not validate_limits(clean): continue

            if is_structural_safe(clean) and '/' in clean:
                parts = clean.split('/', 1)
                prefix_map[parts[0]].add(parts[1])
            else:
                unmergeable.append(clean)

            line_count += 1
            if line_count >= BATCH_LIMIT:
                flush_batch(prefix_map, unmergeable)
                prefix_map.clear()
                unmergeable.clear()
                line_count = 0
                
    if prefix_map or unmergeable:
        flush_batch(prefix_map, unmergeable)
        
    if file_pointer: file_pointer.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: EXEC_HALT. Target filename required as ARG[1].")
        print("USAGE: python script.py <filename.goggles>")
        sys.exit(1)
        
    execute_tier1_chunking(sys.argv[1])