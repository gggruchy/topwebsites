import sys
import os
import re
from typing import List, Tuple

def validate_limits(instruction: str) -> bool:
    """Enforces absolute character and logic gate ceilings."""
    if len(instruction) > 500: return False
    if instruction.count('*') > 2: return False
    if instruction.count('^') > 2: return False
    return True

def translate_to_regex(token: str) -> str:
    """Safely escapes strings while mutating valid operators into regex."""
    escaped = re.escape(token)
    escaped = escaped.replace(r'\*', '.*')
    escaped = escaped.replace(r'\^', r'(?:[^a-zA-Z0-9_%\.-]|$)')
    return escaped

def extract_prefix_suffix(instruction: str) -> Tuple[str, str]:
    """
    Parses structural strings to determine regex mergeability.
    TARGET_LOCK: Explicitly catches and isolates $discard, for regex combination.
    """
    if instruction.startswith('$discard,'):
        return '$discard,', instruction[len('$discard,'):]
        
    if instruction.startswith('/') and instruction.endswith('/'):
        return None, instruction
        
    if any(op in instruction for op in ['||', '@@', '|', '$']):
        return None, instruction
        
    if '/' in instruction:
        parts = instruction.split('/', 1)
        return parts[0] + '/', parts[1]
        
    return None, instruction

def pack_regex_nodes(prefix: str, suffixes: List[str]) -> List[str]:
    """Compiles string alternations bound by the 500-character ceiling."""
    if not prefix: return suffixes
    
    unique_suffixes = list(dict.fromkeys(suffixes))
    if len(unique_suffixes) == 1:
        return [f"{prefix}{unique_suffixes[0]}"]
        
    packed_rules = []
    current_group = []
    
    def compile_group(grp: List[str]) -> str:
        if len(grp) == 1: return f"{prefix}{grp[0]}"
        joined = "|".join(translate_to_regex(s) for s in grp)
        
        # Maps standard regex syntax for $discard, directives
        if prefix == '$discard,':
            return f"{prefix}/({joined})/"
        elif prefix.endswith('/'):
            base_escaped = translate_to_regex(prefix[:-1])
            return f"/{base_escaped}\\/({joined})/"
        return f"{prefix}({joined})"

    for suffix in unique_suffixes:
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
    """
    Executes sequential, top-to-bottom pipeline.
    Max Bytes: 1.9MB Decimal limit. Max Lines: 100,000.
    """
    MAX_LINES = 100000
    MAX_BYTES = 1900000 
    NEWLINE_BYTES = len(os.linesep.encode('utf-8'))
    
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

    def write_rule(rule: str):
        nonlocal current_lines, current_bytes
        rule_bytes = len(rule.encode('utf-8')) + NEWLINE_BYTES
        if current_lines >= MAX_LINES or (current_bytes + rule_bytes) > MAX_BYTES:
            rotate_io()
        file_pointer.write(rule + '\n')
        current_lines += 1
        current_bytes += rule_bytes

    rotate_io()
    
    current_prefix = None
    current_suffixes = []
    
    def flush_buffer():
        if current_suffixes:
            for rule in pack_regex_nodes(current_prefix, current_suffixes):
                write_rule(rule)
            current_suffixes.clear()

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith('!'): continue
            if not validate_limits(clean): continue

            prefix, suffix = extract_prefix_suffix(clean)
            
            # Flushes memory on prefix change to preserve top-to-bottom priority logic
            if prefix != current_prefix or len(current_suffixes) > 1000:
                flush_buffer()
                current_prefix = prefix
                
            current_suffixes.append(suffix)
                
    flush_buffer()
    if file_pointer: file_pointer.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: EXEC_HALT. Target filename required as ARG[1].")
        print("USAGE: python script.py <filename.goggles>")
        sys.exit(1)
        
    execute_tier1_chunking(sys.argv[1])